"""Job type → handler mapping.

Handler contract:
- Do NOT call `session.commit()`: the runner commits the handler's writes together with marking the job
  done, and rolls them back if the handler raises. A mid-handler commit would survive a later failure.
- Be idempotent: a job can run more than once (retry after failure, or reclaim after a worker crash).
- Finish well within WORKER_LOCK_TIMEOUT; a slower job is reclaimed by another worker.

`on_give_up` runs (in its own transaction) when a job fails for the last time, so the owning record
can be marked failed with the error for an operator to see.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

Handler = Callable[[AsyncSession, dict[str, Any]], Awaitable[None]]
GiveUpHook = Callable[[AsyncSession, dict[str, Any], str], Awaitable[None]]


@dataclass(frozen=True)
class JobSpec:
    handler: Handler
    on_give_up: GiveUpHook | None = None


HANDLERS: dict[str, JobSpec] = {}


def register(job_type: str, on_give_up: GiveUpHook | None = None) -> Callable[[Handler], Handler]:
    def decorator(fn: Handler) -> Handler:
        if job_type in HANDLERS:
            raise ValueError(f"handler already registered for job type {job_type!r}")
        HANDLERS[job_type] = JobSpec(fn, on_give_up)
        return fn

    return decorator
