"""Postgres-backed job queue.

Workers claim one job at a time with `FOR UPDATE SKIP LOCKED`, so any number of workers can poll
the same table without taking the same job twice. Failed jobs are retried with exponential backoff
until `max_attempts` is reached; jobs left `running` by a crashed worker are reclaimed after the
lock timeout — unless they are out of attempts (e.g. a job that keeps crashing the worker), in which
case they are marked failed.

Completion updates are fenced on the claim (`locked_at`), so a worker whose job was reclaimed after
the lock timeout cannot overwrite the result of the worker that now owns it.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import ColumnElement, CursorResult, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Job, JobStatus

RETRY_BASE_SECONDS = 30


@dataclass(frozen=True)
class ClaimedJob:
    """Plain snapshot of a claimed job; safe to use after the handler's transaction rolls back."""

    id: int
    type: str
    payload: dict[str, Any]
    attempts: int
    max_attempts: int
    locked_at: datetime


async def enqueue(
    session: AsyncSession,
    job_type: str,
    payload: dict[str, Any] | None = None,
    *,
    delay: timedelta | None = None,
    max_attempts: int = 3,
) -> Job:
    """Add a job. The caller owns the transaction (commit together with related writes)."""
    job = Job(type=job_type, payload=payload or {}, max_attempts=max_attempts)
    if delay is not None:
        job.run_after = func.now() + delay
    session.add(job)
    await session.flush()
    return job


_FAIL_ABANDONED_SQL = text(
    """
    UPDATE jobs SET status = 'failed', locked_at = NULL, updated_at = now(),
        last_error = coalesce(last_error || E'\n', '') || 'abandoned by worker after final attempt'
    WHERE status = 'running'
      AND locked_at < now() - make_interval(secs => :lock_timeout)
      AND attempts >= max_attempts
    """
)

_CLAIM_SQL = text(
    """
    UPDATE jobs SET status = 'running', locked_at = now(), attempts = attempts + 1, updated_at = now()
    WHERE id = (
        SELECT id FROM jobs
        WHERE (status = 'pending' AND run_after <= now())
           OR (status = 'running' AND locked_at < now() - make_interval(secs => :lock_timeout)
               AND attempts < max_attempts)
        ORDER BY run_after, id
        FOR UPDATE SKIP LOCKED
        LIMIT 1
    )
    RETURNING id, type, payload, attempts, max_attempts, locked_at
    """
)


async def claim_next(session: AsyncSession, lock_timeout: int) -> ClaimedJob | None:
    """Fail exhausted abandoned jobs, then atomically take the next runnable job and commit the claim."""
    params = {"lock_timeout": lock_timeout}
    await session.execute(_FAIL_ABANDONED_SQL, params)
    row = (await session.execute(_CLAIM_SQL, params)).one_or_none()
    await session.commit()
    if row is None:
        return None
    return ClaimedJob(row.id, row.type, row.payload, row.attempts, row.max_attempts, row.locked_at)


def _owned(job: ClaimedJob) -> ColumnElement[bool]:
    """Rows still held by this claim (not reclaimed by another worker in the meantime)."""
    return (Job.id == job.id) & (Job.status == JobStatus.RUNNING) & (Job.locked_at == job.locked_at)


async def mark_done(session: AsyncSession, job: ClaimedJob) -> bool:
    """Returns False when the claim was lost (job reclaimed elsewhere); the update is then skipped."""
    result: CursorResult[Any] = await session.execute(  # type: ignore[assignment]
        update(Job).where(_owned(job)).values(status=JobStatus.DONE, locked_at=None, last_error=None)
    )
    await session.commit()
    return bool(result.rowcount)


async def mark_failed(session: AsyncSession, job: ClaimedJob, error: str) -> bool:
    """Schedule a retry with exponential backoff, or fail permanently once attempts are exhausted."""
    if job.attempts < job.max_attempts:
        backoff = timedelta(seconds=RETRY_BASE_SECONDS * 2 ** (job.attempts - 1))
        values: dict[str, Any] = {
            "status": JobStatus.PENDING,
            "run_after": func.now() + backoff,
        }
    else:
        values = {"status": JobStatus.FAILED}
    result: CursorResult[Any] = await session.execute(  # type: ignore[assignment]
        update(Job).where(_owned(job)).values(locked_at=None, last_error=error[:4000], **values)
    )
    await session.commit()
    return bool(result.rowcount)


async def pending_count(session: AsyncSession) -> int:
    stmt = select(func.count()).select_from(Job).where(Job.status == JobStatus.PENDING)
    return (await session.execute(stmt)).scalar_one()
