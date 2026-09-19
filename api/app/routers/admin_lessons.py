"""Admin content API: upload, list, review/edit segments, publish (FR-M2)."""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy import func, select

from app.config import Settings
from app.deps import AdminDep, DbDep, SettingsDep
from app.models import Lesson, Segment
from app.services import lessons as svc
from app.services.audio_probe import InvalidAudio, probe
from app.services.storage import AudioStorage

router = APIRouter(prefix="/admin", tags=["admin"])

Topic = Literal["talk", "news", "interview", "conversation"]
Level = Literal["beginner", "intermediate", "advanced"]


def get_storage(settings: SettingsDep) -> AudioStorage:
    return AudioStorage(settings)


StorageDep = Annotated[AudioStorage, Depends(get_storage)]


class SegmentOut(BaseModel):
    id: int
    idx: int
    text: str
    translation_vi: str
    start_ms: int
    end_ms: int
    word_count_aligned: bool = Field(
        description="Word timings still match the text (split can derive the time)"
    )
    needs_attention: bool
    attention_reason: str


class LessonSummary(BaseModel):
    id: int
    slug: str
    title: str
    topic: str
    level: str
    status: str
    duration_ms: int
    segment_count: int
    attention_count: int
    error_message: str | None
    published_at: datetime | None
    updated_at: datetime


class LessonDetail(LessonSummary):
    source_name: str
    source_url: str
    license: str
    audio_url: str
    transcript: str
    segments: list[SegmentOut]


class LessonUpdate(BaseModel):
    title: Annotated[str, Field(min_length=1, max_length=200)] | None = None
    topic: Topic | None = None
    level: Level | None = None
    source_name: Annotated[str, Field(min_length=1, max_length=200)] | None = None
    source_url: HttpUrl | Literal[""] | None = None
    license: Annotated[str, Field(min_length=1, max_length=200)] | None = None


class SegmentUpdate(BaseModel):
    text: str | None = None
    translation_vi: str | None = None
    start_ms: int | None = None
    end_ms: int | None = None


class MergeRequest(BaseModel):
    first_id: int
    second_id: int


class SplitRequest(BaseModel):
    word_index: int
    split_ms: int | None = None


def _segment_out(s: Segment) -> SegmentOut:
    return SegmentOut(
        id=s.id,
        idx=s.idx,
        text=s.text,
        translation_vi=s.translation_vi,
        start_ms=s.start_ms,
        end_ms=s.end_ms,
        word_count_aligned=len(s.words) == len(s.text.split()),
        needs_attention=s.needs_attention,
        attention_reason=s.attention_reason,
    )


def _summary_fields(lesson: Lesson, segment_count: int, attention_count: int) -> dict[str, object]:
    return {
        "id": lesson.id,
        "slug": lesson.slug,
        "title": lesson.title,
        "topic": lesson.topic,
        "level": lesson.level,
        "status": lesson.status,
        "duration_ms": lesson.duration_ms,
        "segment_count": segment_count,
        "attention_count": attention_count,
        "error_message": lesson.error_message,
        "published_at": lesson.published_at,
        "updated_at": lesson.updated_at,
    }


def _detail(lesson: Lesson, storage: AudioStorage) -> LessonDetail:
    segs = lesson.segments
    return LessonDetail(
        **_summary_fields(lesson, len(segs), sum(s.needs_attention for s in segs)),
        source_name=lesson.source_name,
        source_url=lesson.source_url,
        license=lesson.license,
        audio_url=storage.public_url(lesson.audio_key),
        transcript=lesson.transcript,
        segments=[_segment_out(s) for s in segs],
    )


async def _lesson_or_404(db: DbDep, lesson_id: int) -> Lesson:
    lesson = await svc.load_lesson(db, lesson_id)
    if lesson is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy bài")
    return lesson


def _segment_in(lesson: Lesson, segment_id: int) -> Segment:
    seg = next((s for s in lesson.segments if s.id == segment_id), None)
    if seg is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy câu")
    return seg


async def _lesson_of_segment(db: DbDep, segment_id: int) -> Lesson:
    lesson_id = (
        await db.execute(select(Segment.lesson_id).where(Segment.id == segment_id))
    ).scalar_one_or_none()
    if lesson_id is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy câu")
    return await _lesson_or_404(db, lesson_id)


def _translate_errors(exc: Exception) -> HTTPException:
    if isinstance(exc, svc.LessonConflict):
        return HTTPException(status.HTTP_409_CONFLICT, str(exc))
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc))


async def _read_limited(upload: UploadFile, settings: Settings) -> bytes:
    data = await upload.read(settings.max_audio_bytes + 1)
    if len(data) > settings.max_audio_bytes:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "File âm thanh vượt quá 30 MB")
    return data


@router.get("/lessons", response_model=list[LessonSummary])
async def list_lessons(_: AdminDep, db: DbDep) -> list[LessonSummary]:
    counts = (
        select(
            Segment.lesson_id,
            func.count().label("n"),
            func.count().filter(Segment.needs_attention).label("attention"),
        )
        .group_by(Segment.lesson_id)
        .subquery()
    )
    rows = await db.execute(
        select(Lesson, func.coalesce(counts.c.n, 0), func.coalesce(counts.c.attention, 0))
        .outerjoin(counts, counts.c.lesson_id == Lesson.id)
        .order_by(Lesson.created_at.desc())
    )
    return [LessonSummary(**_summary_fields(lesson, n, a)) for lesson, n, a in rows.tuples()]


@router.post("/lessons", response_model=LessonDetail, status_code=status.HTTP_201_CREATED)
async def create_lesson(
    auth: AdminDep,
    db: DbDep,
    settings: SettingsDep,
    storage: StorageDep,
    title: Annotated[str, Form(min_length=1, max_length=200)],
    topic: Annotated[Topic, Form()],
    level: Annotated[Level, Form()],
    source_name: Annotated[str, Form(min_length=1, max_length=200)],
    license: Annotated[str, Form(min_length=1, max_length=200)],
    transcript: Annotated[str, Form()],
    audio: Annotated[UploadFile, File()],
    source_url: Annotated[HttpUrl | Literal[""], Form()] = "",
) -> LessonDetail:
    """Validate, store the audio, create the lesson in `processing`, enqueue ingestion (AC-M2-01, 02.1)."""
    transcript = transcript.strip()
    if not transcript:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Transcript không được rỗng")
    if len(transcript) > settings.max_transcript_chars:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Transcript vượt quá 20 000 ký tự")
    data = await _read_limited(audio, settings)
    try:
        info = probe(data)
    except InvalidAudio as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None
    if info.duration_ms > settings.max_audio_seconds * 1000:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "File âm thanh dài quá 15 phút")

    key = f"audio/{uuid.uuid4().hex}.{info.extension}"
    await storage.put(key, data, info.content_type)
    lesson = Lesson(
        slug=svc.slugify(title),
        title=title.strip(),
        topic=topic,
        level=level,
        source_name=source_name.strip(),
        source_url=str(source_url),
        license=license.strip(),
        audio_key=key,
        audio_mime=info.content_type,
        duration_ms=info.duration_ms,
        transcript=transcript,
        created_by=auth.user.id,
    )
    try:
        db.add(lesson)
        await db.flush()
        await svc.start_ingest(db, lesson)
        await db.commit()
    except Exception:
        await storage.delete(key)  # don't leave an orphaned audio object behind
        raise
    return _detail(await _lesson_or_404(db, lesson.id), storage)


@router.get("/lessons/{lesson_id}", response_model=LessonDetail)
async def get_lesson(lesson_id: int, _: AdminDep, db: DbDep, storage: StorageDep) -> LessonDetail:
    return _detail(await _lesson_or_404(db, lesson_id), storage)


@router.patch("/lessons/{lesson_id}", response_model=LessonDetail)
async def update_lesson(
    lesson_id: int, body: LessonUpdate, _: AdminDep, db: DbDep, storage: StorageDep
) -> LessonDetail:
    lesson = await _lesson_or_404(db, lesson_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        if value is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"{field} cannot be null")
        setattr(lesson, field, str(value) if field == "source_url" else value)
    await db.commit()
    return _detail(await _lesson_or_404(db, lesson_id), storage)


@router.post("/lessons/{lesson_id}/retry", response_model=LessonDetail)
async def retry_lesson(lesson_id: int, _: AdminDep, db: DbDep, storage: StorageDep) -> LessonDetail:
    lesson = await _lesson_or_404(db, lesson_id)
    try:
        await svc.retry(db, lesson)
    except svc.LessonConflict as exc:
        raise _translate_errors(exc) from None
    await db.commit()
    return _detail(await _lesson_or_404(db, lesson_id), storage)


@router.post("/lessons/{lesson_id}/publish", response_model=LessonDetail)
async def publish_lesson(lesson_id: int, _: AdminDep, db: DbDep, storage: StorageDep) -> LessonDetail:
    lesson = await _lesson_or_404(db, lesson_id)
    try:
        svc.publish(lesson)
    except (svc.LessonConflict, svc.InvalidEdit) as exc:
        raise _translate_errors(exc) from None
    await db.commit()
    return _detail(await _lesson_or_404(db, lesson.id), storage)


@router.post("/lessons/{lesson_id}/unpublish", response_model=LessonDetail)
async def unpublish_lesson(lesson_id: int, _: AdminDep, db: DbDep, storage: StorageDep) -> LessonDetail:
    lesson = await _lesson_or_404(db, lesson_id)
    try:
        svc.unpublish(lesson)
    except svc.LessonConflict as exc:
        raise _translate_errors(exc) from None
    await db.commit()
    return _detail(await _lesson_or_404(db, lesson.id), storage)


@router.patch("/segments/{segment_id}", response_model=LessonDetail)
async def update_segment(
    segment_id: int, body: SegmentUpdate, _: AdminDep, db: DbDep, storage: StorageDep
) -> LessonDetail:
    lesson = await _lesson_of_segment(db, segment_id)
    try:
        svc.edit_segment(lesson, _segment_in(lesson, segment_id), **body.model_dump(exclude_unset=True))
    except (svc.LessonConflict, svc.InvalidEdit) as exc:
        raise _translate_errors(exc) from None
    await db.commit()
    return _detail(await _lesson_or_404(db, lesson.id), storage)


@router.post("/segments/merge", response_model=LessonDetail)
async def merge_segments(body: MergeRequest, _: AdminDep, db: DbDep, storage: StorageDep) -> LessonDetail:
    lesson = await _lesson_of_segment(db, body.first_id)
    try:
        await svc.merge_segments(
            db, lesson, _segment_in(lesson, body.first_id), _segment_in(lesson, body.second_id)
        )
    except (svc.LessonConflict, svc.InvalidEdit) as exc:
        raise _translate_errors(exc) from None
    await db.commit()
    return _detail(await _lesson_or_404(db, lesson.id), storage)


@router.post("/segments/{segment_id}/split", response_model=LessonDetail)
async def split_segment(
    segment_id: int, body: SplitRequest, _: AdminDep, db: DbDep, storage: StorageDep
) -> LessonDetail:
    lesson = await _lesson_of_segment(db, segment_id)
    try:
        await svc.split_segment(db, lesson, _segment_in(lesson, segment_id), body.word_index, body.split_ms)
    except (svc.LessonConflict, svc.InvalidEdit) as exc:
        raise _translate_errors(exc) from None
    await db.commit()
    return _detail(await _lesson_or_404(db, lesson.id), storage)
