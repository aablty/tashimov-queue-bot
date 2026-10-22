import logging

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

logger = logging.getLogger(__name__)


def _error_text(error: BaseException) -> str:
    return str(error).lower()


def is_expired_callback_error(error: BaseException) -> bool:
    text = _error_text(error)
    return "query is too old" in text or "query id is invalid" in text


def is_safe_edit_error(error: BaseException) -> bool:
    text = _error_text(error)
    return any(
        marker in text
        for marker in (
            "message is not modified",
            "message can't be edited",
            "message to edit not found",
        )
    )


def is_safe_delete_error(error: BaseException) -> bool:
    text = _error_text(error)
    return any(
        marker in text
        for marker in (
            "message to delete not found",
            "message can't be deleted",
        )
    )


async def safe_callback_answer(
    callback: CallbackQuery,
    text: str | None = None,
    *,
    show_alert: bool = False,
) -> bool:
    """Answer a callback without failing when Telegram has expired it."""
    try:
        await callback.answer(text, show_alert=show_alert)
    except TelegramBadRequest as exc:
        if not is_expired_callback_error(exc):
            raise
        logger.debug("Ignoring expired callback query: data=%s", callback.data)
        return False
    return True


async def safe_edit_text(
    message: Message,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> bool:
    """Edit a bot message and ignore harmless stale-message races."""
    try:
        await message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest as exc:
        if not is_safe_edit_error(exc):
            raise
        logger.debug("Ignoring safe message edit race: %s", exc)
        return False
    return True


async def safe_edit_text_by_id(
    bot: Bot,
    chat_id: int,
    message_id: int,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> Message | bool | None:
    """Edit a message by identifier and ignore harmless stale-message races."""
    try:
        return await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            reply_markup=reply_markup,
        )
    except TelegramBadRequest as exc:
        if not is_safe_edit_error(exc):
            raise
        logger.debug("Ignoring safe message edit race: %s", exc)
        return None


async def safe_delete(message: Message) -> bool:
    """Delete a message when possible and ignore already-gone messages."""
    try:
        await message.delete()
    except TelegramForbiddenError as exc:
        logger.debug("Ignoring message delete without permissions: %s", exc)
        return False
    except TelegramBadRequest as exc:
        if not is_safe_delete_error(exc):
            raise
        logger.debug("Ignoring safe message delete race: %s", exc)
        return False
    return True


async def safe_delete_by_id(bot: Bot, chat_id: int, message_id: int) -> bool:
    """Delete a message by identifier while ignoring already-gone messages."""
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except TelegramBadRequest as exc:
        if not is_safe_delete_error(exc):
            raise
        logger.debug("Ignoring safe message delete race: %s", exc)
        return False
    return True
