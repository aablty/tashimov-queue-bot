import asyncio
import unittest
from unittest.mock import AsyncMock

from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import GetMe

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
        callback = type("Callback", (), {})()
        callback.data = "menu:help"
        callback.answer = AsyncMock(
            side_effect=telegram_bad_request("query is too old")
        )

        result = asyncio.run(safe_callback_answer(callback))

        self.assertFalse(result)
        callback.answer.assert_awaited_once()

    def test_unexpected_callback_error_is_re_raised(self) -> None:
        callback = type("Callback", (), {})()
        callback.data = "menu:help"
        callback.answer = AsyncMock(
            side_effect=telegram_bad_request("can't parse InlineKeyboardButton")
        )

        with self.assertRaises(TelegramBadRequest):
            asyncio.run(safe_callback_answer(callback))

    def test_unmodified_edit_is_ignored(self) -> None:
        message = type("Message", (), {})()
        message.edit_text = AsyncMock(
            side_effect=telegram_bad_request("message is not modified")
        )

        result = asyncio.run(safe_edit_text(message, "same"))

        self.assertFalse(result)
        message.edit_text.assert_awaited_once_with("same", reply_markup=None)


if __name__ == "__main__":
    unittest.main()
