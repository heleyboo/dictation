from dataclasses import dataclass, field
from typing import Any

import pytest
from pydantic import BaseModel
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Job, Lesson, LessonStatus, LlmUsage
from app.services import lessons
from app.services.llm_client import LlmError
from app.services.segmentation import AlignedWord
from app.services.translation import TranslationBatch
from app.worker import handlers
from app.worker.handlers import ingest
from app.worker.registry import HANDLERS
from app.worker.runner import run_one

TRANSCRIPT = "Scientists say the study matters. It was published today."
WORDS = [
    ("Scientists", 0, 700), ("say", 800, 1000), ("the", 1100, 1200), ("study", 1300, 1700),
    ("matters.", 1800, 2400), ("It", 3000, 3200), ("was", 3300, 3500), ("published", 3600, 4200),
    ("today.", 4300, 4900),
]  # fmt: skip


@dataclass
class FakeLlm:
    """Translates by echoing; can be told to fail or to drop sentences."""

    fail_times: int = 0
    drop: set[int] = field(default_factory=set)
    calls: int = 0

    async def parse(
        self, db: AsyncSession, *, purpose: str, system: str, prompt: str, schema: type[Any]
    ) -> Any:
        self.calls += 1
        db.add(LlmUsage(purpose=purpose, model="fake", input_tokens=10, output_tokens=5))
        if self.calls <= self.fail_times:
            raise LlmError("refused")
        lines = prompt.split("Hãy dịch các câu sau, trả về đúng từng `idx`:\n", 1)[1].splitlines()
        items = []
        for line in lines:
            idx, sentence = line.split(": ", 1)
            if int(idx) not in self.drop:
                items.append({"idx": int(idx), "vi": f"VI[{sentence}]"})
        assert issubclass(schema, BaseModel)
        return TranslationBatch.model_validate({"translations": items})


@pytest.fixture
def fakes(monkeypatch: pytest.MonkeyPatch) -> FakeLlm:
    assert handlers.ingest is ingest  # handlers are registered
    llm = FakeLlm()

    class Storage:
        async def get(self, key: str) -> bytes:
            return b"RIFF-fake-audio"

    def align(path: str, transcript: str, model: str) -> list[AlignedWord]:
        assert transcript == TRANSCRIPT and path.endswith(".wav")
        return [AlignedWord(f" {t}", s, e, 0.9) for t, s, e in WORDS]

    monkeypatch.setattr(
        ingest, "deps", ingest.IngestDeps(storage=lambda: Storage(), llm=lambda: llm, align=align)
    )
    return llm


async def _new_lesson(sessions: async_sessionmaker[AsyncSession]) -> int:
    async with sessions() as db:
        lesson = Lesson(
            slug="s", title="Sleep", topic="news", level="beginner", source_name="VOA", license="PD",
            audio_key="audio/x.wav", audio_mime="audio/wav", duration_ms=6000, transcript=TRANSCRIPT,
        )  # fmt: skip
        db.add(lesson)
        await db.flush()
        await lessons.start_ingest(db, lesson)
        await db.commit()
        return lesson.id


async def _drain(sessions: async_sessionmaker[AsyncSession]) -> None:
    while await run_one(sessions, 900, HANDLERS):
        pass


async def _lesson(sessions: async_sessionmaker[AsyncSession], lesson_id: int) -> Lesson:
    async with sessions() as db:
        lesson = await lessons.load_lesson(db, lesson_id)
        assert lesson is not None
        return lesson


async def test_pipeline_aligns_translates_and_moves_to_review(
    sessions: async_sessionmaker[AsyncSession], fakes: FakeLlm
) -> None:
    lesson_id = await _new_lesson(sessions)
    await _drain(sessions)
    lesson = await _lesson(sessions, lesson_id)
    assert lesson.status == LessonStatus.REVIEW
    assert [(s.idx, s.text, s.start_ms, s.end_ms) for s in lesson.segments] == [
        (0, "Scientists say the study matters.", 0, 2850),
        (1, "It was published today.", 2850, 5400),
    ]
    assert lesson.segments[0].translation_vi == "VI[Scientists say the study matters.]"
    assert lesson.segments[1].words[2] == {
        "word": "published",
        "start_ms": 3600,
        "end_ms": 4200,
        "probability": 0.9,
    }
    async with sessions() as db:
        assert (await db.execute(select(LlmUsage.purpose))).scalars().all() == ["translate"]


async def test_translation_retried_once_on_bad_answer(
    sessions: async_sessionmaker[AsyncSession], fakes: FakeLlm
) -> None:
    fakes.fail_times = 1
    lesson_id = await _new_lesson(sessions)
    await _drain(sessions)
    assert (await _lesson(sessions, lesson_id)).status == LessonStatus.REVIEW
    assert fakes.calls == 2


async def test_lesson_marked_failed_after_retries_exhausted(
    sessions: async_sessionmaker[AsyncSession], fakes: FakeLlm
) -> None:
    fakes.drop = {1}  # the model keeps leaving out a sentence
    lesson_id = await _new_lesson(sessions)
    for _ in range(3):  # 3 attempts; make retries due immediately
        await _drain(sessions)
        async with sessions() as db:
            await db.execute(update(Job).where(Job.status == "pending").values(run_after=text("now()")))
            await db.commit()
    lesson = await _lesson(sessions, lesson_id)
    assert lesson.status == LessonStatus.FAILED
    assert "missing sentences [1]" in (lesson.error_message or "")
    # alignment output survives a translation failure; admin can retry
    assert len(lesson.segments) == 2


async def test_rerun_replaces_segments_idempotently(
    sessions: async_sessionmaker[AsyncSession], fakes: FakeLlm
) -> None:
    lesson_id = await _new_lesson(sessions)
    await _drain(sessions)
    async with sessions() as db:
        await db.execute(update(Lesson).values(status=LessonStatus.FAILED))
        await db.commit()
        lesson = await lessons.load_lesson(db, lesson_id)
        assert lesson is not None
        await lessons.retry(db, lesson)
        await db.commit()
    await _drain(sessions)
    lesson = await _lesson(sessions, lesson_id)
    assert lesson.status == LessonStatus.REVIEW and len(lesson.segments) == 2
