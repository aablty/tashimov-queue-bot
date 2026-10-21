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
    def __init__(self, teacher_id: int) -> None:
        self.teacher_id = teacher_id

    async def __call__(self, message: Message) -> bool:
        return message.from_user is not None and message.from_user.id == self.teacher_id
