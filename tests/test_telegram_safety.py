import asyncio
import unittest
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock

from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import GetMe
from aiogram.types import CallbackQuery, Message

from src.bot.utils.telegram import (
    is_expired_callback_error,
    is_safe_delete_error,
    is_safe_edit_error,
    safe_callback_answer,
    safe_edit_text,
)


def telegram_bad_request(message: str) -> TelegramBadRequest:
    return TelegramBadRequest(method=GetMe(), message=message)


class TelegramSafetyTests(unittest.TestCase):
    def test_classifies_only_expected_callback_errors(self) -> None:
        self.assertTrue(is_expired_callback_error(Exception("query is too old")))
        self.assertTrue(is_expired_callback_error(Exception("query ID is invalid")))
        self.assertFalse(is_expired_callback_error(Exception("invalid markup")))

    def test_classifies_safe_message_operations(self) -> None:
        self.assertTrue(is_safe_edit_error(Exception("message is not modified")))
        self.assertTrue(is_safe_edit_error(Exception("message can't be edited")))
        self.assertTrue(is_safe_delete_error(Exception("message to delete not found")))
        self.assertFalse(
            is_safe_edit_error(Exception("can't parse InlineKeyboardButton"))
        )

    def test_expired_callback_is_ignored(self) -> None:
        answer = AsyncMock(side_effect=telegram_bad_request("query is too old"))
        callback = cast(
            CallbackQuery,
            SimpleNamespace(data="menu:help", answer=answer),
        )

        result = asyncio.run(safe_callback_answer(callback))

        self.assertFalse(result)
        answer.assert_awaited_once()

    def test_unexpected_callback_error_is_re_raised(self) -> None:
        answer = AsyncMock(
            side_effect=telegram_bad_request("can't parse InlineKeyboardButton")
        )
        callback = cast(
            CallbackQuery,
            SimpleNamespace(data="menu:help", answer=answer),
        )

        with self.assertRaises(TelegramBadRequest):
            asyncio.run(safe_callback_answer(callback))

    def test_unmodified_edit_is_ignored(self) -> None:
        edit_text = AsyncMock(
            side_effect=telegram_bad_request("message is not modified")
        )
        message = cast(Message, SimpleNamespace(edit_text=edit_text))

        result = asyncio.run(safe_edit_text(message, "same"))

        self.assertFalse(result)
        edit_text.assert_awaited_once_with("same", reply_markup=None)


if __name__ == "__main__":
    unittest.main()
