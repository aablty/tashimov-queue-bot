from typing import Any

from aiogram.types import Update

from src.api.core.base_service import BaseService, ServiceResponse
from src.bot import bot, dp


class WebhooksService(BaseService):
    async def webhook_handler(self, body: Any) -> ServiceResponse:
        update = Update.model_validate(body, context={"bot": bot})
        await dp.feed_update(bot, update)

        return self.ok({"ok": True})
