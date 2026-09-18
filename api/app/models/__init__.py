"""Import every model here so Alembic sees the full metadata."""

from app.models.base import Base
from app.models.job import Job, JobStatus
from app.models.user import MagicLink, Role, Session, User

__all__ = ["Base", "Job", "JobStatus", "MagicLink", "Role", "Session", "User"]
