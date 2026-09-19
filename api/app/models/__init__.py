"""Import every model here so Alembic sees the full metadata."""

from app.models.base import Base
from app.models.job import Job, JobStatus
from app.models.lesson import LEVELS, TOPICS, Lesson, LessonStatus, LlmUsage, Segment
from app.models.user import MagicLink, Role, Session, User

__all__ = [
    "LEVELS",
    "TOPICS",
    "Base",
    "Job",
    "JobStatus",
    "Lesson",
    "LessonStatus",
    "LlmUsage",
    "MagicLink",
    "Role",
    "Segment",
    "Session",
    "User",
]
