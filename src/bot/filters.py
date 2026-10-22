from collections.abc import Collection

from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message


class GroupOnly(BaseFilter):
    async def __call__(self, event: Message | CallbackQuery) -> bool:
        chat = (
            event.chat
            if isinstance(event, Message)
            else event.message.chat
            if event.message
            else None
        )
        return chat is not None and chat.type in {"group", "supergroup"}


class TeacherOnly(BaseFilter):
    def __init__(self, teacher_ids: int | Collection[int]) -> None:
        self.teacher_ids = (
            {teacher_ids} if isinstance(teacher_ids, int) else set(teacher_ids)
        )

    async def __call__(self, message: Message) -> bool:
        return (
            message.from_user is not None and message.from_user.id in self.teacher_ids
        )
