import asyncio
import logging

from .queue import QueueRepository

logger = logging.getLogger(__name__)


async def lifecycle_loop() -> None:
    repository = QueueRepository()
    while True:
        try:
            await repository.sync_all()
        except Exception:
            logger.exception("Queue lifecycle tick failed")
        finally:
            await asyncio.sleep(60)
