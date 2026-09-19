from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

TOPICS = ("talk", "news", "interview", "conversation")
LEVELS = ("beginner", "intermediate", "advanced")


class LessonStatus:
    """draft → processing → review → published (+ failed, unpublished). SRS FR-M2."""

    PROCESSING = "processing"
    REVIEW = "review"
    PUBLISHED = "published"
    FAILED = "failed"
    UNPUBLISHED = "unpublished"


class Lesson(TimestampMixin, Base):
    __tablename__ = "lessons"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    slug: Mapped[str] = mapped_column(String(160), unique=True)
    title: Mapped[str] = mapped_column(String(200))
    topic: Mapped[str] = mapped_column(String(16))
    level: Mapped[str] = mapped_column(String(16))
    source_name: Mapped[str] = mapped_column(String(200))
    source_url: Mapped[str] = mapped_column(String(1000), default="")
    license: Mapped[str] = mapped_column(String(200))
    audio_key: Mapped[str] = mapped_column(String(200))
    audio_mime: Mapped[str] = mapped_column(String(64))
    duration_ms: Mapped[int] = mapped_column(Integer)
    transcript: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default=LessonStatus.PROCESSING, index=True)
    error_message: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    segments: Mapped[list["Segment"]] = relationship(
        back_populates="lesson", order_by="Segment.idx", cascade="all, delete-orphan"
    )


class Segment(Base):
    """One dictation sentence with its audio span. `words` holds per-word timings from alignment."""

    __tablename__ = "segments"
    # Deferred so merge/split can renumber `idx` inside one transaction.
    __table_args__ = (
        UniqueConstraint(
            "lesson_id", "idx", name="uq_segments_lesson_idx", deferrable=True, initially="DEFERRED"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"), index=True)
    idx: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    translation_vi: Mapped[str] = mapped_column(Text, default="")
    start_ms: Mapped[int] = mapped_column(Integer)
    end_ms: Mapped[int] = mapped_column(Integer)
    # [{"word": str, "start_ms": int, "end_ms": int, "probability": float}, ...]
    words: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    needs_attention: Mapped[bool] = mapped_column(Boolean, default=False)
    attention_reason: Mapped[str] = mapped_column(String(200), default="")

    lesson: Mapped[Lesson] = relationship(back_populates="segments")


class LlmUsage(Base):
    """One row per LLM call, for cost tracking (NFR-11, NFR-12)."""

    __tablename__ = "llm_usage"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    purpose: Mapped[str] = mapped_column(String(32))
    model: Mapped[str] = mapped_column(String(64))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
