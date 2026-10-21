from html import escape

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from src.bot import bot
from src.bot.filters import GroupOnly, TeacherOnly
from src.bot.utils.telegram import (
    safe_callback_answer,
    safe_edit_text_by_id,
)
from src.core.config import config
from src.db.queue import (
    AlreadyReservedError,
    NotReservedError,
    QueueAlreadyExistsError,
    QueueClosedError,
    QueueError,
    QueueRepository,
    SlotUnavailableError,
)

router = Router(name="queue")
repository = QueueRepository()


def render_queue(queue) -> str:
    slots = sorted(queue.slots, key=lambda slot: slot.position)
    occupied_slots = [slot for slot in slots if slot.user_id is not None]
    occupied = len(occupied_slots)
    state = "активна" if queue.status == "active" else "закрыта"
    lines = [f"<b>Очередь</b> · {state}", f"Занято: {occupied}/{queue.capacity}", ""]
    if not occupied_slots:
        lines.append("Пока никто не записался.")
    else:
        for index, slot in enumerate(occupied_slots, start=1):
            name = escape(slot.user_name or str(slot.user_id))
            user_link = f'<a href="tg://user?id={slot.user_id}">{name}</a>'
            lines.append(f"{index}. {user_link}")
    return "\n".join(lines)


def queue_markup(queue) -> InlineKeyboardMarkup:
    if queue.status != "active":
        return InlineKeyboardMarkup(inline_keyboard=[])

    free_positions = [
        slot.position
        for slot in sorted(queue.slots, key=lambda item: item.position)
        if slot.user_id is None
    ]
    rows = [
        [
            InlineKeyboardButton(
                text=str(position),
                callback_data=f"queue:book:{queue.id}:{position}",
            )
            for position in free_positions[index : index + 5]
        ]
        for index in range(0, len(free_positions), 5)
    ]
    rows.append(
        [
            InlineKeyboardButton(
                text="Освободить моё место",
                callback_data=f"queue:release:{queue.id}",
            ),
            InlineKeyboardButton(
                text="Обновить",
                callback_data=f"queue:refresh:{queue.id}",
            ),
        ]
    )
    rows.append(
        [
            InlineKeyboardButton(
                text="Закрыть очередь",
                callback_data=f"queue:close:{queue.id}",
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def send_queue(message: Message, queue) -> None:
    if queue.message_id is None:
        sent = await message.answer(
            render_queue(queue), reply_markup=queue_markup(queue)
        )
        queue.message_id = sent.message_id
        await queue.save(update_fields=("message_id",))
    else:
        await safe_edit_text_by_id(
            bot,
            queue.chat_id,
            queue.message_id,
            render_queue(queue),
            queue_markup(queue),
        )


@router.message(Command("queue"), GroupOnly(), TeacherOnly(config.TEACHER_ID))
async def queue_command(message: Message, command: CommandObject) -> None:
    argument = (command.args or "").strip().lower()
    active = await repository.get_active(message.chat.id)
    if not argument:
        if active is None:
            await message.answer("Активной очереди нет.")
            return
        await send_queue(message, active)
        return
    if argument == "close":
        if active is None:
            await message.answer("Активной очереди нет.")
            return
        await repository.close(active.id)
        closed = await repository.get(active.id)
        if closed is not None and closed.message_id is not None:
            await safe_edit_text_by_id(
                bot, closed.chat_id, closed.message_id, render_queue(closed)
            )
        await message.answer("Очередь закрыта.")
        return
    if not argument.isdigit():
        await message.answer(
            f"Использование: /queue N (1–{config.QUEUE_MAX_SLOTS}) или /queue close."
        )
        return
    capacity = int(argument)
    if not 1 <= capacity <= config.QUEUE_MAX_SLOTS:
        await message.answer(
            f"Количество слотов должно быть от 1 до {config.QUEUE_MAX_SLOTS}."
        )
        return
    if message.from_user is None:
        return
    try:
        queue = await repository.create(message.chat.id, message.from_user.id, capacity)
    except QueueAlreadyExistsError:
        await message.answer("В этой группе уже есть активная очередь.")
        return
    await send_queue(message, queue)


@router.message(Command("queue"), GroupOnly())
async def queue_show(message: Message) -> None:
    queue = await repository.get_active(message.chat.id)
    if queue is None:
        await message.answer("Активной очереди нет.")
        return
    await send_queue(message, queue)


@router.callback_query(F.data.startswith("queue:book:"), GroupOnly())
async def book_slot(callback: CallbackQuery) -> None:
    if callback.message is None or callback.from_user is None or callback.data is None:
        return
    _, _, queue_id, position = callback.data.split(":")
    try:
        await repository.reserve(
            int(queue_id),
            int(position),
            callback.from_user.id,
            callback.from_user.full_name,
            callback.from_user.username,
        )
        await safe_callback_answer(callback, "Слот занят.")
    except AlreadyReservedError:
        await safe_callback_answer(callback, "У вас уже есть слот.", show_alert=True)
        return
    except (QueueClosedError, SlotUnavailableError, ValueError):
        await safe_callback_answer(
            callback, "Этот слот уже недоступен.", show_alert=True
        )
        return
    queue = await repository.get(int(queue_id))
    if queue is not None:
        await safe_edit_text_by_id(
            bot,
            callback.message.chat.id,
            callback.message.message_id,
            render_queue(queue),
            queue_markup(queue),
        )


@router.callback_query(F.data.startswith("queue:release:"), GroupOnly())
async def release_slot(callback: CallbackQuery) -> None:
    if callback.message is None or callback.from_user is None or callback.data is None:
        return
    _, _, queue_id = callback.data.split(":")
    try:
        await repository.release(int(queue_id), callback.from_user.id)
        await safe_callback_answer(callback, "Слот освобождён.")
    except NotReservedError:
        await safe_callback_answer(
            callback, "У вас нет занятого слота.", show_alert=True
        )
        return
    except (QueueClosedError, ValueError):
        await safe_callback_answer(callback, "Очередь закрыта.", show_alert=True)
        return
    queue = await repository.get(int(queue_id))
    if queue is not None:
        await safe_edit_text_by_id(
            bot,
            callback.message.chat.id,
            callback.message.message_id,
            render_queue(queue),
            queue_markup(queue),
        )


@router.callback_query(F.data.startswith("queue:refresh:"), GroupOnly())
async def refresh_queue(callback: CallbackQuery) -> None:
    if callback.message is None or callback.data is None:
        return
    _, _, queue_id = callback.data.split(":")
    queue = await repository.get(int(queue_id))
    if queue is None:
        await safe_callback_answer(callback, "Очередь не найдена.", show_alert=True)
        return
    await safe_callback_answer(callback)
    await safe_edit_text_by_id(
        bot,
        callback.message.chat.id,
        callback.message.message_id,
        render_queue(queue),
        queue_markup(queue),
    )


@router.callback_query(F.data.startswith("queue:close:"), GroupOnly())
async def close_queue_callback(callback: CallbackQuery) -> None:
    if callback.message is None or callback.data is None:
        return
    if callback.from_user is None or callback.from_user.id != config.TEACHER_ID:
        await safe_callback_answer(
            callback, "Закрыть очередь может только преподаватель.", show_alert=True
        )
        return
    _, _, queue_id = callback.data.split(":")
    try:
        queue = await repository.close(int(queue_id))
    except (QueueError, ValueError):
        await safe_callback_answer(callback, "Очередь не найдена.", show_alert=True)
        return
    await safe_callback_answer(callback, "Очередь закрыта.")
    queue = await repository.get(queue.id)
    if queue is not None:
        await safe_edit_text_by_id(
            bot,
            callback.message.chat.id,
            callback.message.message_id,
            render_queue(queue),
            queue_markup(queue),
        )
