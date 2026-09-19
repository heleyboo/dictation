"""Lesson ingestion pipeline: align transcript to audio → segments → translate → ready for review.

Two jobs so a translation failure retries without redoing the (slow) alignment.
"""

import asyncio
import logging
import os
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import LessonStatus, Segment
from app.services import alignment, lessons
from app.services.llm_client import AnthropicLlm, StructuredLlm
from app.services.segmentation import AlignedWord, build_segments, split_sentences
from app.services.storage import AudioStorage
from app.services.translation import translate_sentences
from app.worker import queue
from app.worker.registry import register

log = logging.getLogger("worker.ingest")

TRANSLATE_JOB = "translate_lesson"
ERROR_LIMIT = 2000


class AudioReader(Protocol):
    async def get(self, key: str) -> bytes: ...


@dataclass
class IngestDeps:
    """External services used by the pipeline; tests swap these for fakes."""

    storage: Callable[[], AudioReader]
    llm: Callable[[], StructuredLlm]
    align: Callable[[str, str, str], list[AlignedWord]]


def _default_deps() -> IngestDeps:
    return IngestDeps(
        storage=lambda: AudioStorage(get_settings()),
        llm=lambda: AnthropicLlm(get_settings().llm_model),
        align=alignment.align,
    )


deps = _default_deps()


async def _mark_failed(db: AsyncSession, payload: dict[str, Any], error: str) -> None:
    lesson = await lessons.load_lesson(db, int(payload["lesson_id"]))
    if lesson is not None and lesson.status == LessonStatus.PROCESSING:
        lesson.status = LessonStatus.FAILED
        lesson.error_message = error[:ERROR_LIMIT]


@register(lessons.INGEST_JOB, on_give_up=_mark_failed)
async def ingest_lesson(db: AsyncSession, payload: dict[str, Any]) -> None:
    lesson = await lessons.load_lesson(db, int(payload["lesson_id"]))
    if lesson is None or lesson.status != LessonStatus.PROCESSING:
        log.info("skip ingest for lesson %s (missing or not processing)", payload.get("lesson_id"))
        return

    sentences = split_sentences(lesson.transcript)
    if not sentences:
        raise ValueError("transcript has no sentences")
    audio = await deps.storage().get(lesson.audio_key)
    suffix = os.path.splitext(lesson.audio_key)[1]
    with tempfile.NamedTemporaryFile(suffix=suffix) as tmp:
        tmp.write(audio)
        tmp.flush()
        aligned = await asyncio.to_thread(
            deps.align, tmp.name, " ".join(sentences), get_settings().align_model
        )
    if not aligned:
        raise ValueError("alignment returned no words")

    drafts = build_segments(sentences, aligned, lesson.duration_ms)
    # Idempotent re-run: replace whatever a previous attempt left behind.
    await db.execute(delete(Segment).where(Segment.lesson_id == lesson.id))
    lesson.segments = [
        Segment(
            idx=i,
            text=d.text,
            start_ms=d.start_ms,
            end_ms=d.end_ms,
            words=[
                {"word": w.word, "start_ms": w.start_ms, "end_ms": w.end_ms, "probability": w.probability}
                for w in d.words
            ],
            needs_attention=d.needs_attention,
            attention_reason=d.attention_reason,
        )
        for i, d in enumerate(drafts)
    ]
    await queue.enqueue(db, TRANSLATE_JOB, {"lesson_id": lesson.id})
    log.info("lesson %s aligned into %s segments", lesson.id, len(drafts))


@register(TRANSLATE_JOB, on_give_up=_mark_failed)
async def translate_lesson(db: AsyncSession, payload: dict[str, Any]) -> None:
    lesson = await lessons.load_lesson(db, int(payload["lesson_id"]))
    if lesson is None or lesson.status != LessonStatus.PROCESSING or not lesson.segments:
        log.info("skip translate for lesson %s", payload.get("lesson_id"))
        return
    translations = await translate_sentences(deps.llm(), lesson.title, [s.text for s in lesson.segments])
    for segment, vi in zip(lesson.segments, translations, strict=True):
        segment.translation_vi = vi
    lesson.status = LessonStatus.REVIEW
    log.info("lesson %s translated; ready for review", lesson.id)
