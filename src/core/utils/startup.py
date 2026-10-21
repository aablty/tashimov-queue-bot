import logging
import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from aiogram.types import BotCommand, BotCommandScopeDefault
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from tortoise import Tortoise

from src import api
from src.bot import bot, dp, handlers
from src.bot.middleware import TelegramResilienceMiddleware

from ..config import config


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(name)s - %(message)s",
        stream=sys.stdout,
        force=True,
    )


def setup_app(app: FastAPI) -> None:
    app.include_router(api.router())
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[config.API_URL],
        allow_methods=["*"],
        allow_headers=["*"],
    )


async def setup_bot() -> None:
    dp.include_router(handlers.router())
    dp.update.outer_middleware(TelegramResilienceMiddleware())
    await bot.set_my_commands(
        [
            BotCommand(command="q", description="Очередь: показать или создать"),
            BotCommand(command="queue", description="То же, полная команда"),
        ],
        scope=BotCommandScopeDefault(),
    )
    await bot.set_webhook(
        url=f"{config.API_URL}/webhook",
        secret_token=config.APP_API_KEY.get_secret_value(),
        drop_pending_updates=True,
        allowed_updates=dp.resolve_used_update_types(),
    )


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator:
    configure_logging()
    await Tortoise.init(config=config.tortoise_orm, _enable_global_fallback=True)
    try:
        await setup_bot()
    except Exception:
        await Tortoise.close_connections()
        raise
    try:
        yield
    finally:
        await bot.session.close()
        await Tortoise.close_connections()
