"""Admin-side lesson lifecycle and segment editing (FR-M2-01, FR-M2-03, FR-M2-04)."""

import re
import secrets
import unicodedata
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Lesson, LessonStatus, Segment
from app.worker import queue

INGEST_JOB = "ingest_lesson"

EDITABLE = {LessonStatus.REVIEW, LessonStatus.UNPUBLISHED, LessonStatus.PUBLISHED}
RESTRUCTURABLE = {LessonStatus.REVIEW, LessonStatus.UNPUBLISHED}


class LessonConflict(Exception):
    """The operation is not allowed in the lesson's current state (HTTP 409)."""


class InvalidEdit(ValueError):
    """The requested edit is malformed (HTTP 422)."""


def slugify(title: str) -> str:
    ascii_title = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    base = re.sub(r"[^a-z0-9]+", "-", ascii_title.lower()).strip("-")[:120] or "lesson"
    return f"{base}-{secrets.token_hex(3)}"


async def start_ingest(db: AsyncSession, lesson: Lesson) -> None:
    lesson.status = LessonStatus.PROCESSING
    lesson.error_message = None
    await queue.enqueue(db, INGEST_JOB, {"lesson_id": lesson.id})


async def load_lesson(db: AsyncSession, lesson_id: int) -> Lesson | None:
    return (
        await db.execute(
            select(Lesson)
            .where(Lesson.id == lesson_id)
            .options(selectinload(Lesson.segments))
            # Refresh objects already in the session (e.g. server-side `updated_at` after a commit).
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()


async def retry(db: AsyncSession, lesson: Lesson) -> None:
    if lesson.status != LessonStatus.FAILED:
        raise LessonConflict("Chỉ chạy lại được bài đang lỗi")
    await start_ingest(db, lesson)


def _neighbours(lesson: Lesson, seg: Segment) -> tuple[Segment | None, Segment | None]:
    by_idx = {s.idx: s for s in lesson.segments}
    return by_idx.get(seg.idx - 1), by_idx.get(seg.idx + 1)


def validate_timing(lesson: Lesson, seg: Segment, start_ms: int, end_ms: int) -> None:
    if not 0 <= start_ms < end_ms <= lesson.duration_ms:
        raise InvalidEdit("Thời gian phải thoả 0 ≤ start < end ≤ thời lượng bài")
    prev, nxt = _neighbours(lesson, seg)
    if prev is not None and start_ms < prev.end_ms:
        raise InvalidEdit(f"Chồng lấn câu {prev.idx + 1} (kết thúc {prev.end_ms} ms)")
    if nxt is not None and end_ms > nxt.start_ms:
        raise InvalidEdit(f"Chồng lấn câu {nxt.idx + 1} (bắt đầu {nxt.start_ms} ms)")


def edit_segment(
    lesson: Lesson,
    seg: Segment,
    *,
    text: str | None = None,
    translation_vi: str | None = None,
    start_ms: int | None = None,
    end_ms: int | None = None,
) -> None:
    """Text/translation/timing edits keep the segment id, so learner progress survives (AC-M2-04.3)."""
    if lesson.status not in EDITABLE:
        raise LessonConflict("Bài chưa sẵn sàng để chỉnh sửa")
    if text is not None:
        if not text.strip():
            raise InvalidEdit("Câu không được rỗng")
        seg.text = text.strip()
    if translation_vi is not None:
        seg.translation_vi = translation_vi.strip()
    if start_ms is not None or end_ms is not None:
        new_start = seg.start_ms if start_ms is None else start_ms
        new_end = seg.end_ms if end_ms is None else end_ms
        validate_timing(lesson, seg, new_start, new_end)
        seg.start_ms, seg.end_ms = new_start, new_end


async def _shift(db: AsyncSession, lesson_id: int, after_idx: int, delta: int) -> None:
    await db.execute(
        update(Segment)
        .where(Segment.lesson_id == lesson_id, Segment.idx > after_idx)
        .values(idx=Segment.idx + delta)
    )


async def merge_segments(db: AsyncSession, lesson: Lesson, first: Segment, second: Segment) -> Segment:
    if lesson.status not in RESTRUCTURABLE:
        raise LessonConflict("Phải bỏ đăng bài trước khi gộp/tách câu")
    if first.lesson_id != lesson.id or second.lesson_id != lesson.id or second.idx != first.idx + 1:
        raise InvalidEdit("Chỉ gộp được hai câu liền kề trong cùng bài")
    first.text = f"{first.text} {second.text}"
    first.translation_vi = " ".join(t for t in (first.translation_vi, second.translation_vi) if t)
    first.end_ms = second.end_ms
    first.words = [*first.words, *second.words]
    first.needs_attention = first.needs_attention or second.needs_attention
    first.attention_reason = first.attention_reason or second.attention_reason
    removed_idx = second.idx
    lesson.segments.remove(second)
    await db.delete(second)
    await db.flush()
    await _shift(db, lesson.id, removed_idx, -1)
    return first


async def split_segment(
    db: AsyncSession, lesson: Lesson, seg: Segment, word_index: int, split_ms: int | None = None
) -> Segment:
    """Split before `word_index`. The cut time comes from word alignment when it still matches the text."""
    if lesson.status not in RESTRUCTURABLE:
        raise LessonConflict("Phải bỏ đăng bài trước khi gộp/tách câu")
    tokens = seg.text.split()
    if not 1 <= word_index < len(tokens):
        raise InvalidEdit("Vị trí tách phải nằm giữa câu")
    if split_ms is None:
        if len(seg.words) != len(tokens):
            raise InvalidEdit("Câu đã sửa chữ nên không còn mốc thời gian theo từ — hãy nhập split_ms")
        split_ms = int(seg.words[word_index]["start_ms"])
    if not seg.start_ms < split_ms < seg.end_ms:
        raise InvalidEdit("Mốc tách phải nằm trong câu")

    await _shift(db, lesson.id, seg.idx, +1)
    aligned = len(seg.words) == len(tokens)
    tail = Segment(
        lesson_id=lesson.id,
        idx=seg.idx + 1,
        text=" ".join(tokens[word_index:]),
        translation_vi="",
        start_ms=split_ms,
        end_ms=seg.end_ms,
        words=seg.words[word_index:] if aligned else [],
        needs_attention=True,
        attention_reason="Cần dịch lại sau khi tách",
    )
    seg.text = " ".join(tokens[:word_index])
    seg.end_ms = split_ms
    seg.words = seg.words[:word_index] if aligned else []
    seg.needs_attention = True
    seg.attention_reason = "Cần dịch lại sau khi tách"
    lesson.segments.insert(lesson.segments.index(seg) + 1, tail)
    await db.flush()
    return tail


def publish(lesson: Lesson) -> None:
    if lesson.status not in RESTRUCTURABLE:
        raise LessonConflict("Chỉ đăng được bài đang chờ duyệt hoặc đã bỏ đăng")
    if not lesson.segments:
        raise InvalidEdit("Bài chưa có câu nào")
    missing = [s.idx + 1 for s in lesson.segments if not s.text.strip() or not s.translation_vi.strip()]
    if missing:
        raise InvalidEdit(f"Câu thiếu nội dung hoặc bản dịch: {missing[:10]}")
    lesson.status = LessonStatus.PUBLISHED
    lesson.published_at = datetime.now(UTC)


def unpublish(lesson: Lesson) -> None:
    if lesson.status != LessonStatus.PUBLISHED:
        raise LessonConflict("Bài chưa được đăng")
    lesson.status = LessonStatus.UNPUBLISHED
