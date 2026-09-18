"""Worker loop: claim → run handler → mark done/failed."""

import asyncio
import logging
import traceback
from collections.abc import Mapping

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.worker import queue
from app.worker.registry import HANDLERS, Handler

log = logging.getLogger("worker")


async def run_one(
    sessions: async_sessionmaker[AsyncSession],
    lock_timeout: int,
    handlers: Mapping[str, Handler] | None = None,
) -> bool:
    """Process at most one job. Returns False when nothing was claimable."""
    handlers = HANDLERS if handlers is None else handlers
    async with sessions() as session:
        job = await queue.claim_next(session, lock_timeout)
        if job is None:
            return False
        handler = handlers.get(job.type)
        if handler is None:
            log.error("no handler for job type %s (job %s)", job.type, job.id)
            await queue.mark_failed(session, job, f"no handler registered for {job.type!r}")
            return True
        log.info("running job %s type=%s attempt=%s", job.id, job.type, job.attempts)
        try:
            await handler(session, job.payload)
        except Exception:  # noqa: BLE001 — any handler failure is recorded on the job, never crashes the loop
            await session.rollback()
            log.exception("job %s failed", job.id)
            await queue.mark_failed(session, job, traceback.format_exc())
        else:
            if not await queue.mark_done(session, job):
                log.warning("job %s finished after its claim was lost (reclaimed elsewhere)", job.id)
        return True


async def run_forever(
    sessions: async_sessionmaker[AsyncSession], poll_interval: float, lock_timeout: int, stop: asyncio.Event
) -> None:
    log.info("worker started (poll=%ss, handlers=%s)", poll_interval, sorted(HANDLERS))
    while not stop.is_set():
        try:
            worked = await run_one(sessions, lock_timeout)
        except Exception:  # noqa: BLE001 — e.g. DB briefly unreachable; keep polling
            log.exception("worker loop error")
            worked = False
        if not worked:
            try:
                await asyncio.wait_for(stop.wait(), timeout=poll_interval)
            except TimeoutError:
                log.debug("heartbeat")
    log.info("worker stopped")
