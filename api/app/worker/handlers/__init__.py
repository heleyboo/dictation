"""Importing this package registers every job handler."""

from app.worker.handlers import ingest

__all__ = ["ingest"]
