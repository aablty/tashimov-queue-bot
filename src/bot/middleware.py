import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import TelegramObject

from src.bot.utils.telegram import (
    is_expired_callback_error,
    is_safe_delete_error,
    is_safe_edit_error,
)

logger = logging.getLogger(__name__)


class TelegramResilienceMiddleware(BaseMiddleware):
    """Last-resort protection for harmless Telegram races in handlers."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        try:
            return await handler(event, data)
        except TelegramBadRequest as exc:
            if not (
                is_expired_callback_error(exc)
                or is_safe_edit_error(exc)
                or is_safe_delete_error(exc)
            ):
                raise
            logger.debug("Ignored harmless Telegram race in update: %s", exc)
            return None
