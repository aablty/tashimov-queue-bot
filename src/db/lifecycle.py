import asyncio
import logging

from .queue import QueueRepository

logger = logging.getLogger(__name__)


TICK_INTERVAL_SECONDS = 600
"""shortcut: tuned for ~100 Neon CU-hrs/month on a 5-min autosuspend; lower it if
queues need fresher background cleanup and the budget allows it."""


async def lifecycle_loop() -> None:
    repository = QueueRepository()
    while True:
        try:
            await repository.sync_all()
        except Exception:
            logger.exception("Queue lifecycle tick failed")
        finally:
            await asyncio.sleep(TICK_INTERVAL_SECONDS)
