"""Entrypoint: `python -m app.worker`."""

import asyncio
import logging
import signal

from app.config import get_settings
from app.db import get_engine, session_factory
from app.worker.runner import run_forever


async def main() -> None:
    settings = get_settings()
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    try:
        await run_forever(
            session_factory(), settings.worker_poll_interval, settings.worker_lock_timeout, stop
        )
    finally:
        await get_engine().dispose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    asyncio.run(main())
