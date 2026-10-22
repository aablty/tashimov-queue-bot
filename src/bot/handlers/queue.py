from __future__ import annotations

from datetime import UTC, date, datetime
from html import escape
from typing import Any
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import (
    CallbackQuery,
    DisabledButton,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from src.bot import bot
from src.bot.filters import GroupOnly, TeacherOnly
from src.bot.utils.emoji import PremiumEmoji
from src.bot.utils.telegram import safe_callback_answer, safe_edit_text_by_id
from src.core.config import config
from src.db.models import Queue, QueueSchedule
from src.db.queue import (
    AlreadyReservedError,
    NotReservedError,
    QueueClosedError,
    QueueError,
    QueueRepository,
    SlotUnavailableError,
    queue_grace_deadline,
)

router = Router(name="queue")
repository = QueueRepository()
WEEKDAYS = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб")


def button(text: str, data: str, style: str | None = None, icon: str = "") -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data, style=style, icon_custom_emoji_id=icon or None)


def empty_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[])


def local_zone() -> ZoneInfo:
    return ZoneInfo(config.QUEUE_TIMEZONE)


def payload_of(draft: Any) -> dict[str, Any]:
    return dict(draft.payload or {})


def time_text(start: int, end: int) -> str:
    return f"{start // 60:02d}:{start % 60:02d}–{end // 60:02d}:{end % 60:02d}"


def weekday_text(value: int | None) -> str:
    return WEEKDAYS[value] if value is not None and 0 <= value < len(WEEKDAYS) else "не выбран"


def schedule_payload(schedule: QueueSchedule) -> dict[str, Any]:
    return {
        "schedule_id": schedule.id,
        "kind": schedule.kind,
        "name": schedule.name,
        "once_date": schedule.once_date.isoformat() if schedule.once_date else None,
        "weekday": schedule.weekday,
        "start_minute": schedule.start_minute,
        "end_minute": schedule.end_minute,
        "capacity": schedule.capacity,
    }


def setup_text(payload: dict[str, Any], step: str) -> str:
    if step == "main":
        return "<b>Расписания группы</b>\n\nВыберите очередь для редактирования или создайте новую."
    if step == "review":
        period = payload.get("once_date") if payload.get("kind") == "once" else weekday_text(payload.get("weekday"))
        return (
            f"<b>{escape(str(payload.get('name') or 'Очередь'))}</b>\n"
            f"Тип: {'разовая' if payload.get('kind') == 'once' else 'еженедельная'}\n"
            f"Когда: {period}\n"
            f"Время: {time_text(payload['start_minute'], payload['end_minute'])}\n"
            f"Мест: {payload['capacity']}"
        )
    if step == "main":
        return "<b>Расписания группы</b>"
    kind = "разовая" if payload.get("kind") == "once" else "еженедельная"
    if payload.get("kind") == "once":
        period = payload.get("once_date") or "не выбрана"
    else:
        period = weekday_text(payload.get("weekday"))
    current_time = time_text(payload["start_minute"], payload["end_minute"]) if payload.get("start_minute") is not None and payload.get("end_minute") is not None else "не выбран"
    return (
        "<b>Настройка очереди</b>\n\n"
        f"Название: <b>{escape(str(payload.get('name') or 'не задано'))}</b>\n"
        f"Тип: <b>{kind}</b>\nПериод: <b>{period}</b>\n"
        f"Время: <b>{current_time}</b>\nМест: <b>{payload.get('capacity') or 'не выбрано'}</b>\n\n"
        + {
            "kind": "Выберите тип очереди:",
            "name": "Отправьте название очереди следующим сообщением.",
            "date": "Выберите дату:",
            "day": "Выберите день недели:",
            "start": "Выберите начало:",
            "end": "Выберите конец:",
            "capacity": "Выберите количество мест:",
        }.get(step, "Настройка очереди")
    )


def setup_markup(payload: dict[str, Any], step: str) -> InlineKeyboardMarkup:
    if step == "main":
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [button("Новая очередь", "qsetup:new", icon=PremiumEmoji.ADD_QUEUE.value)],
                *[
                    [
                        button(
                            f"{item['name'][:20]} · {time_text(item['start_minute'], item['end_minute'])}",
                            f"qsetup:edit:{item['schedule_id']}",
                        )
                    ]
                    for item in payload.get("schedules", [])
                ],
            ]
        )
    if step == "review":
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [button("Изменить", f"qsetup:editform:{payload['schedule_id']}")],
                [button("Удалить", f"qsetup:delete:{payload['schedule_id']}", icon=PremiumEmoji.REMOVE_QUEUE.value)],
                [button("Назад", "qsetup:main", icon=PremiumEmoji.BACK.value)],
            ]
        )
    if step == "kind":
        return InlineKeyboardMarkup(inline_keyboard=[[button("Разовая", "qsetup:kind:once"), button("Еженедельная", "qsetup:kind:weekly")]])
    if step == "name":
        return InlineKeyboardMarkup(inline_keyboard=[[button("Назад", "qsetup:back:kind", icon=PremiumEmoji.BACK.value)]])
    if step == "date":
        today = datetime.now(local_zone()).date()
        return InlineKeyboardMarkup(inline_keyboard=[[
            button((today.fromordinal(today.toordinal() + i)).strftime("%d.%m"), f"qsetup:date:{i}") for i in range(7)
        ], [button("Назад", "qsetup:back:name", icon=PremiumEmoji.BACK.value)]])
    if step == "day":
        return InlineKeyboardMarkup(inline_keyboard=[
            [button(label, f"qsetup:day:{index}") for index, label in enumerate(WEEKDAYS)],
            [button("Назад", "qsetup:back:name", icon=PremiumEmoji.BACK.value)],
        ])
    if step == "start":
        return InlineKeyboardMarkup(inline_keyboard=[
            [button(f"{hour:02d}:00", f"qsetup:start:{hour}") for hour in range(12)],
            [button(f"{hour:02d}:00", f"qsetup:start:{hour}") for hour in range(12, 24)],
            [button("Назад", "qsetup:back:period", icon=PremiumEmoji.BACK.value)],
        ])
    if step == "end":
        first = int(payload.get("start_minute", 0)) // 60 + 1
        return InlineKeyboardMarkup(inline_keyboard=[
            [button(f"{hour:02d}:00", f"qsetup:end:{hour}") for hour in range(first, 12)],
            [button(f"{hour:02d}:00", f"qsetup:end:{hour}") for hour in range(max(12, first), 24)],
            [button("Назад", "qsetup:back:start", icon=PremiumEmoji.BACK.value)],
        ])
    values = [1, 5, 10, 15, 20, 25, 50, config.QUEUE_MAX_SLOTS]
    return InlineKeyboardMarkup(inline_keyboard=[
        [button(str(value), f"qsetup:capacity:{value}") for value in dict.fromkeys(values) if value <= config.QUEUE_MAX_SLOTS],
        [button("Назад", "qsetup:back:end", icon=PremiumEmoji.BACK.value)],
    ])


async def edit_setup(draft: Any) -> None:
    if draft.message_id is not None:
        payload = payload_of(draft)
        await safe_edit_text_by_id(bot, draft.chat_id, draft.message_id, setup_text(payload, draft.step), setup_markup(payload, draft.step))


async def start_setup(message: Message) -> None:
    if message.from_user is None:
        return
    draft = await repository.create_draft(message.chat.id, message.from_user.id)
    schedules = await repository.list_schedules(message.chat.id)
    payload: dict[str, Any] = {"kind": "weekly", "name": ""}
    step = "kind"
    if schedules:
        payload["schedules"] = [schedule_payload(schedule) for schedule in schedules]
        step = "main"
    sent = await message.answer(setup_text(payload, step), reply_markup=setup_markup(payload, step))
    await repository.save_draft(draft, step=step, payload=payload, message_id=sent.message_id)


@router.message(Command("q"), GroupOnly(), TeacherOnly(config.teacher_ids))
async def queue_command(message: Message, command: CommandObject) -> None:
    if (command.args or "").strip():
        await message.answer("Используйте /q для настройки очередей или /qs для просмотра.")
        return
    await start_setup(message)


@router.message(Command("qs"), GroupOnly())
async def queues_command(message: Message) -> None:
    queues = await repository.list_queues(message.chat.id)
    await message.answer(render_queue_list(queues), reply_markup=list_markup(queues))


@router.message(F.text, GroupOnly(), TeacherOnly(config.teacher_ids))
async def setup_name(message: Message) -> None:
    draft = await repository.get_draft(message.chat.id)
    if draft is None or draft.step != "name" or not message.text or message.text.startswith("/"):
        return
    payload = payload_of(draft)
    payload["name"] = message.text.strip()[:255] or "Очередь"
    await repository.save_draft(draft, step="date" if payload["kind"] == "once" else "day", payload=payload)
    await edit_setup(draft)


@router.callback_query(F.data.startswith("qsetup:"), GroupOnly())
async def setup_callback(callback: CallbackQuery) -> None:
    if callback.message is None or callback.data is None:
        return
    draft = await repository.get_draft(callback.message.chat.id)
    if draft is None or callback.from_user is None or callback.from_user.id != draft.teacher_id:
        await safe_callback_answer(callback, "Настройка устарела.", show_alert=True)
        return
    parts = callback.data.split(":")
    action = parts[1]
    payload = payload_of(draft)
    if action == "main":
        schedules = await repository.list_schedules(draft.chat_id)
        payload = {"schedules": [schedule_payload(schedule) for schedule in schedules]}
        await repository.save_draft(draft, step="main", payload=payload)
    elif action == "new":
        await repository.save_draft(draft, step="kind", payload={"kind": "weekly", "name": ""})
    elif action in {"edit", "editform"}:
        schedule = await repository.get_schedule(int(parts[2]))
        if schedule is None:
            await safe_callback_answer(callback, "Очередь удалена.", show_alert=True)
            return
        await repository.save_draft(draft, step="review" if action == "edit" else "kind", payload=schedule_payload(schedule))
    elif action == "delete":
        await repository.delete_schedule(int(parts[2]))
        schedules = await repository.list_schedules(draft.chat_id)
        await repository.save_draft(draft, step="main", payload={"schedules": [schedule_payload(schedule) for schedule in schedules]})
    elif action == "kind":
        payload["kind"] = parts[2]
        await repository.save_draft(draft, step="name", payload=payload)
    elif action == "back":
        target = parts[2]
        if target == "period":
            target = "date" if payload["kind"] == "once" else "day"
        await repository.save_draft(draft, step=target, payload=payload)
    elif action == "date":
        today = datetime.now(local_zone()).date()
        payload["once_date"] = today.fromordinal(today.toordinal() + int(parts[2])).isoformat()
        await repository.save_draft(draft, step="start", payload=payload)
    elif action == "day":
        payload["weekday"] = int(parts[2])
        await repository.save_draft(draft, step="start", payload=payload)
    elif action == "start":
        payload["start_minute"] = int(parts[2]) * 60
        await repository.save_draft(draft, step="end", payload=payload)
    elif action == "end":
        payload["end_minute"] = int(parts[2]) * 60
        await repository.save_draft(draft, step="capacity", payload=payload)
    elif action == "capacity":
        payload["capacity"] = min(int(parts[2]), config.QUEUE_MAX_SLOTS)
        values: dict[str, Any] = {
            "name": str(payload["name"]),
            "kind": str(payload["kind"]),
            "once_date": date.fromisoformat(payload["once_date"]) if payload.get("once_date") else None,
            "weekday": int(payload["weekday"]) if payload.get("weekday") is not None else None,
            "start_minute": int(payload["start_minute"]),
            "end_minute": int(payload["end_minute"]),
            "capacity": int(payload["capacity"]),
            "timezone": config.QUEUE_TIMEZONE,
        }
        if payload.get("schedule_id"):
            await repository.update_schedule(int(payload["schedule_id"]), **values)
        else:
            await repository.create_schedule(
                chat_id=draft.chat_id,
                teacher_id=draft.teacher_id,
                name=str(values["name"]),
                kind=str(values["kind"]),
                once_date=values["once_date"],
                weekday=values["weekday"],
                start_minute=values["start_minute"],
                end_minute=values["end_minute"],
                capacity=values["capacity"],
                timezone=str(values["timezone"]),
            )
        await draft.delete()
        await safe_callback_answer(callback, "Сохранено.")
        await safe_edit_text_by_id(bot, callback.message.chat.id, callback.message.message_id, "<b>Очередь сохранена.</b>\n\nОткрыть очереди: /qs", empty_markup())
        return
    await safe_callback_answer(callback)
    await edit_setup(draft)


def render_queue(queue: Any, *, closed: bool = False) -> str:
    slots = sorted(queue.slots, key=lambda slot: slot.position)
    occupied = [slot for slot in slots if slot.user_id is not None]
    starts_at = getattr(queue, "starts_at", None)
    when = starts_at.astimezone(local_zone()).strftime("%H:%M") if starts_at else ""
    ends_at = getattr(queue, "ends_at", None)
    state = "закрыта" if closed or (ends_at is not None and queue_grace_deadline(ends_at) <= datetime.now(UTC)) else "активна"
    lines = [f"<b>{escape(getattr(queue, 'name', 'Очередь'))}</b> · {state} · {when}", f"Занято: {len(occupied)}/{queue.capacity}", ""]
    lines.extend(f'{index}. <a href="tg://user?id={slot.user_id}">{escape(slot.user_name or str(slot.user_id))}</a>' for index, slot in enumerate(occupied, 1))
    return "\n".join(lines or ["Пока никто не записался."])


def queue_markup(queue: Any) -> InlineKeyboardMarkup:
    ends_at = getattr(queue, "ends_at", None)
    if ends_at is not None and queue_grace_deadline(ends_at) <= datetime.now(UTC):
        return empty_markup()
    slots = sorted(queue.slots, key=lambda item: item.position)
    rows = [[InlineKeyboardButton(text=str(slot.position), style="success" if slot.user_id is None else "primary", callback_data=f"queue:book:{queue.id}:{slot.position}" if slot.user_id is None else None, disabled=DisabledButton() if slot.user_id is not None else None) for slot in slots[index:index + 5]] for index in range(0, len(slots), 5)]
    rows += [[button("Освободить", f"queue:release:{queue.id}", icon=PremiumEmoji.RELEASE_SLOT.value), button("Обновить", f"queue:refresh:{queue.id}", icon=PremiumEmoji.REFRESH_QUEUE.value)], [button("К списку", "qs:list", icon=PremiumEmoji.BACK.value)]]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def render_queue_list(queues: list[Queue]) -> str:
    return "<b>Очереди на текущую неделю</b>\n\nВыберите очередь:" if queues else "<b>Очереди на текущую неделю</b>\n\nОчередей нет."


def list_markup(queues: list[Queue]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                button(
                    f"{queue.name[:24]} · {WEEKDAYS[queue.starts_at.astimezone(local_zone()).weekday()]} {queue.starts_at.astimezone(local_zone()):%H:%M}",
                    f"qs:open:{queue.id}",
                )
            ]
            for queue in queues
            if queue.starts_at
        ]
    )


async def stale(callback: CallbackQuery) -> None:
    await safe_callback_answer(callback, "Очередь уже завершена или удалена.", show_alert=True)
    if callback.message is not None:
        await safe_edit_text_by_id(bot, callback.message.chat.id, callback.message.message_id, "<b>Очередь завершена или удалена.</b>", empty_markup())


@router.callback_query(F.data.startswith("qs:"), GroupOnly())
async def queues_callback(callback: CallbackQuery) -> None:
    if callback.message is None or callback.data is None:
        return
    if callback.data == "qs:list":
        queues = await repository.list_queues(callback.message.chat.id)
        await safe_callback_answer(callback)
        await safe_edit_text_by_id(bot, callback.message.chat.id, callback.message.message_id, render_queue_list(queues), list_markup(queues))
        return
    queue = await repository.get(int(callback.data.split(":")[2]))
    if queue is None:
        await stale(callback)
        return
    await safe_callback_answer(callback)
    await safe_edit_text_by_id(bot, callback.message.chat.id, callback.message.message_id, render_queue(queue), queue_markup(queue))


@router.callback_query(F.data.startswith("queue:book:"), GroupOnly())
async def book_slot(callback: CallbackQuery) -> None:
    if callback.message is None or callback.from_user is None or callback.data is None:
        return
    _, _, queue_id, position = callback.data.split(":")
    try:
        await repository.reserve(int(queue_id), int(position), callback.from_user.id, callback.from_user.full_name, callback.from_user.username)
    except AlreadyReservedError:
        await safe_callback_answer(callback, "У вас уже есть слот.", show_alert=True)
        return
    except SlotUnavailableError:
        await safe_callback_answer(callback, "Слот уже занят.", show_alert=True)
        return
    except (QueueClosedError, QueueError, ValueError):
        await stale(callback)
        return
    queue = await repository.get(int(queue_id))
    if queue is None:
        await stale(callback)
        return
    await safe_callback_answer(callback, "Слот занят.")
    await safe_edit_text_by_id(bot, callback.message.chat.id, callback.message.message_id, render_queue(queue), queue_markup(queue))


@router.callback_query(F.data.startswith("queue:release:"), GroupOnly())
async def release_slot(callback: CallbackQuery) -> None:
    if callback.message is None or callback.from_user is None or callback.data is None:
        return
    queue_id = int(callback.data.split(":")[2])
    try:
        await repository.release(queue_id, callback.from_user.id)
    except NotReservedError:
        await safe_callback_answer(callback, "У вас нет занятого слота.", show_alert=True)
        return
    except (QueueClosedError, QueueError, ValueError):
        await stale(callback)
        return
    queue = await repository.get(queue_id)
    if queue is None:
        await stale(callback)
        return
    await safe_callback_answer(callback, "Слот освобождён.")
    await safe_edit_text_by_id(bot, callback.message.chat.id, callback.message.message_id, render_queue(queue), queue_markup(queue))


@router.callback_query(F.data.startswith("queue:refresh:"), GroupOnly())
async def refresh_queue(callback: CallbackQuery) -> None:
    if callback.message is None or callback.data is None:
        return
    queue = await repository.get(int(callback.data.split(":")[2]))
    if queue is None:
        await stale(callback)
        return
    await safe_callback_answer(callback)
    await safe_edit_text_by_id(bot, callback.message.chat.id, callback.message.message_id, render_queue(queue), queue_markup(queue))
