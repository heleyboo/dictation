"""Import every model here so Alembic sees the full metadata."""

from app.models.base import Base
from app.models.job import Job, JobStatus

__all__ = ["Base", "Job", "JobStatus"]
