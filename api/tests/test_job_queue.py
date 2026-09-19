import asyncio
from collections import Counter
from typing import Any

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Job, JobStatus
from app.worker import queue
from app.worker.registry import JobSpec
from app.worker.runner import run_one

LOCK_TIMEOUT = 900


async def _enqueue_many(sessions: async_sessionmaker[AsyncSession], n: int, job_type: str = "t") -> None:
    async with sessions() as session:
        for i in range(n):
            await queue.enqueue(session, job_type, {"n": i})
        await session.commit()


async def _drain(sessions: async_sessionmaker[AsyncSession], handlers: dict[str, JobSpec]) -> None:
    while await run_one(sessions, LOCK_TIMEOUT, handlers):
        pass


async def _statuses(sessions: async_sessionmaker[AsyncSession]) -> list[Job]:
    async with sessions() as session:
        return list((await session.execute(select(Job).order_by(Job.id))).scalars())


async def test_two_workers_run_each_job_exactly_once(sessions: async_sessionmaker[AsyncSession]) -> None:
    await _enqueue_many(sessions, 20)
    runs: Counter[int] = Counter()

    async def handler(_: AsyncSession, payload: dict[str, Any]) -> None:
        runs[payload["n"]] += 1
        await asyncio.sleep(0.01)  # widen the race window between workers

    await asyncio.gather(_drain(sessions, {"t": JobSpec(handler)}), _drain(sessions, {"t": JobSpec(handler)}))

    assert runs == Counter({i: 1 for i in range(20)})
    assert {j.status for j in await _statuses(sessions)} == {JobStatus.DONE}


async def test_failed_job_is_retried_with_backoff_then_fails(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    await _enqueue_many(sessions, 1)

    async def boom(_: AsyncSession, __: dict[str, Any]) -> None:
        raise RuntimeError("handler exploded")

    handlers = {"t": JobSpec(boom)}
    for expected_attempts in (1, 2, 3):
        assert await run_one(sessions, LOCK_TIMEOUT, handlers)
        [job] = await _statuses(sessions)
        assert job.attempts == expected_attempts
        assert "handler exploded" in (job.last_error or "")
        if expected_attempts < 3:
            assert job.status == JobStatus.PENDING
            # backoff: not claimable yet
            assert not await run_one(sessions, LOCK_TIMEOUT, handlers)
            async with sessions() as session:
                await session.execute(update(Job).values(run_after=text("now()")))
                await session.commit()

    [job] = await _statuses(sessions)
    assert job.status == JobStatus.FAILED
    assert not await run_one(sessions, LOCK_TIMEOUT, handlers)


async def test_handler_writes_roll_back_on_failure(sessions: async_sessionmaker[AsyncSession]) -> None:
    await _enqueue_many(sessions, 1)

    async def half_done(session: AsyncSession, _: dict[str, Any]) -> None:
        await queue.enqueue(session, "side-effect")
        raise RuntimeError("fail after writing")

    await run_one(sessions, LOCK_TIMEOUT, {"t": JobSpec(half_done)})
    assert [j.type for j in await _statuses(sessions)] == ["t"]


async def test_unknown_job_type_is_recorded_not_crashing(sessions: async_sessionmaker[AsyncSession]) -> None:
    await _enqueue_many(sessions, 1, job_type="nope")
    assert await run_one(sessions, LOCK_TIMEOUT, {})
    [job] = await _statuses(sessions)
    assert "no handler registered" in (job.last_error or "")


async def test_abandoned_running_job_is_reclaimed(sessions: async_sessionmaker[AsyncSession]) -> None:
    await _enqueue_many(sessions, 1)
    async with sessions() as session:
        await session.execute(
            update(Job).values(
                status=JobStatus.RUNNING, locked_at=text("now() - interval '1 hour'"), attempts=1
            )
        )
        await session.commit()

    seen: list[int] = []

    async def handler(_: AsyncSession, payload: dict[str, Any]) -> None:
        seen.append(payload["n"])

    assert await run_one(sessions, LOCK_TIMEOUT, {"t": JobSpec(handler)})
    assert seen == [0]
    [job] = await _statuses(sessions)
    assert (job.status, job.attempts) == (JobStatus.DONE, 2)


async def test_delayed_job_waits_for_run_after(sessions: async_sessionmaker[AsyncSession]) -> None:
    from datetime import timedelta

    async with sessions() as session:
        await queue.enqueue(session, "t", delay=timedelta(hours=1))
        await session.commit()
        assert await queue.pending_count(session) == 1
    assert not await run_one(sessions, LOCK_TIMEOUT, {"t": JobSpec(lambda *_: asyncio.sleep(0))})


async def test_abandoned_job_out_of_attempts_is_failed_not_rerun(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    await _enqueue_many(sessions, 1)
    async with sessions() as session:
        await session.execute(
            update(Job).values(
                status=JobStatus.RUNNING,
                locked_at=text("now() - interval '1 hour'"),
                attempts=3,
                max_attempts=3,
            )
        )
        await session.commit()

    ran: list[int] = []

    async def handler(_: AsyncSession, payload: dict[str, Any]) -> None:
        ran.append(payload["n"])

    assert not await run_one(sessions, LOCK_TIMEOUT, {"t": JobSpec(handler)})
    assert ran == []
    [job] = await _statuses(sessions)
    assert job.status == JobStatus.FAILED
    assert "abandoned by worker" in (job.last_error or "")


async def test_worker_that_lost_its_claim_cannot_overwrite_result(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    await _enqueue_many(sessions, 1)
    async with sessions() as session:
        stale = await queue.claim_next(session, LOCK_TIMEOUT)
        assert stale is not None
        # Simulate the lock timing out and another worker reclaiming the job.
        await session.execute(update(Job).values(locked_at=text("now() - interval '1 hour'")))
        await session.commit()
        fresh = await queue.claim_next(session, LOCK_TIMEOUT)
        assert fresh is not None and fresh.id == stale.id and fresh.locked_at != stale.locked_at

        assert not await queue.mark_done(session, stale)
        assert not await queue.mark_failed(session, stale, "late failure")
        [job] = await _statuses(sessions)
        assert (job.status, job.attempts, job.last_error) == (JobStatus.RUNNING, 2, None)

        assert await queue.mark_done(session, fresh)
    [job] = await _statuses(sessions)
    assert job.status == JobStatus.DONE


async def test_give_up_hook_runs_once_after_final_attempt(sessions: async_sessionmaker[AsyncSession]) -> None:
    async with sessions() as session:
        await queue.enqueue(session, "t", {"n": 7}, max_attempts=2)
        await session.commit()
    gave_up: list[tuple[dict[str, Any], str]] = []

    async def boom(_: AsyncSession, __: dict[str, Any]) -> None:
        raise ValueError("bad input")

    async def give_up(_: AsyncSession, payload: dict[str, Any], error: str) -> None:
        gave_up.append((payload, error))

    spec = {"t": JobSpec(boom, give_up)}
    assert await run_one(sessions, LOCK_TIMEOUT, spec)
    assert gave_up == []  # retry pending
    async with sessions() as session:
        await session.execute(update(Job).values(run_after=text("now()")))
        await session.commit()
    assert await run_one(sessions, LOCK_TIMEOUT, spec)
    assert gave_up == [({"n": 7}, "ValueError: bad input")]
