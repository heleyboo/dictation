"""Job type → handler mapping. Later phases register handlers here (e.g. `ingest_lesson`).

Handler contract:
- Do NOT call `session.commit()`: the runner commits the handler's writes together with marking the job
  done, and rolls them back if the handler raises. A mid-handler commit would survive a later failure.
- Be idempotent: a job can run more than once (retry after failure, or reclaim after a worker crash).
- Finish well within WORKER_LOCK_TIMEOUT; a slower job is reclaimed by another worker.
"""

from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

Handler = Callable[[AsyncSession, dict[str, Any]], Awaitable[None]]

HANDLERS: dict[str, Handler] = {}


def register(job_type: str) -> Callable[[Handler], Handler]:
    def decorator(fn: Handler) -> Handler:
        if job_type in HANDLERS:
            raise ValueError(f"handler already registered for job type {job_type!r}")
        HANDLERS[job_type] = fn
        return fn

    return decorator
