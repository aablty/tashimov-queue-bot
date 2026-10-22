from __future__ import annotations

from datetime import date, datetime
from html import escape
from typing import Any, cast
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
)

router = Router(name="queue")
repository = QueueRepository()


def b(
    text: str, data: str, style: str | None = None, icon: str = ""
) -> InlineKeyboardButton:
    return InlineKeyboardButton(
        text=text, callback_data=data, style=style, icon_custom_emoji_id=icon or None
    )


def empty_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[])


def payload_of(draft) -> dict:
    return dict(draft.payload or {})


def setup_text(payload: dict, step: str) -> str:
    if step == "main":
        items = (
            "\n".join(
                f"• {escape(item['name'])}" for item in payload.get("schedules", [])
            )
            or "Пока нет расписаний."
        )
        return f"<b>Расписания группы</b>\n\n{items}\n\nВыберите действие:"
    kind = "разовая" if payload.get("kind") == "once" else "еженедельная"
    name = escape(payload.get("name") or "не задано")
    if payload.get("kind") == "once":
        period = payload.get("once_date") or "не выбрана"
    else:
        labels = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
        period = (
            ", ".join(labels[i] for i in payload.get("weekdays") or []) or "не выбраны"
        )
    intervals = payload.get("intervals") or []
    interval_text = (
        "\n".join(
            f"• {item['start_minute'] // 60:02d}:{item['start_minute'] % 60:02d}–{item['end_minute'] // 60:02d}:{item['end_minute'] % 60:02d}, {item['capacity']} мест"
            for item in intervals
        )
        or "пока нет"
    )
    prompts = {
        "kind": "Выберите тип расписания:",
        "name": "Отправьте название очереди следующим сообщением.",
        "date": "Выберите дату:",
        "days": "Выберите дни недели, затем нажмите «Готово»:",
        "intervals": "Добавьте временные интервалы:",
        "start": "Выберите начало интервала:",
        "end": "Выберите конец интервала:",
        "step": "Выберите режим интервала:",
        "capacity": "Выберите вместимость:",
    }
    return f"<b>Настройка очереди</b>\n\nНазвание: <b>{name}</b>\nТип: <b>{kind}</b>\nПериод: <b>{period}</b>\nИнтервалы:\n{interval_text}\n\n{prompts.get(step, 'Настройка очереди')}"


def setup_markup(payload: dict, step: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if step == "main":
        rows = [[b("＋ Новая очередь", "qsetup:new")]]
        rows.extend(
            [
                [
                    b(item["name"][:24], f"qsetup:edit:{item['id']}"),
                    b("Удалить", f"qsetup:delete:{item['id']}"),
                ]
                for item in payload.get("schedules", [])
            ]
        )
    elif step == "kind":
        rows = [
            [b("Разовая", "qsetup:kind:once"), b("Еженедельная", "qsetup:kind:weekly")]
        ]
    elif step == "name":
        rows = [[b("Назад", "qsetup:back:kind")]]
    elif step == "date":
        today = datetime.now(ZoneInfo(config.QUEUE_TIMEZONE)).date()
        rows = [
            [
                b(
                    today.fromordinal(today.toordinal() + i).isoformat(),
                    f"qsetup:date:{i}",
                )
                for i in range(7)
            ],
            [b("Назад", "qsetup:back:kind")],
        ]
    elif step == "days":
        labels = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
        selected = set(payload.get("weekdays") or [])
        rows = [
            [
                b(("✓ " if i in selected else "") + label, f"qsetup:day:{i}")
                for i, label in enumerate(labels)
            ],
            [
                b("Готово", "qsetup:days:done", "success"),
                b("Назад", "qsetup:back:kind"),
            ],
        ]
    elif step == "intervals":
        rows = [[b("＋ Добавить интервал", "qsetup:add")]]
        rows.extend(
            [
                [b(f"✕ Удалить интервал {index + 1}", f"qsetup:remove:{index}")]
                for index, _ in enumerate(payload.get("intervals") or [])
            ]
        )
        if payload.get("intervals"):
            rows.append([b("✓ Сохранить", "qsetup:save", "success")])
        rows.append([b("Назад", "qsetup:back:kind")])
    elif step == "start":
        rows = [
            [b(f"{h:02d}:00", f"qsetup:start:{h}") for h in range(12)],
            [b(f"{h:02d}:00", f"qsetup:start:{h}") for h in range(12, 24)],
            [b("Назад", "qsetup:back:intervals")],
        ]
    elif step == "end":
        first = payload.get("draft_start", 0) // 60 + 1
        rows = [
            [b(f"{h:02d}:00", f"qsetup:end:{h}") for h in range(first, 12)],
            [b(f"{h:02d}:00", f"qsetup:end:{h}") for h in range(max(12, first), 24)],
            [b("Назад", "qsetup:back:start")],
        ]
    elif step == "step":
        rows = [
            [
                b("Один интервал", "qsetup:step:single"),
                b("Каждый час", "qsetup:step:hour"),
            ],
            [b("Назад", "qsetup:back:end")],
        ]
    elif step == "capacity":
        values = [1, 5, 10, 15, 20, 25, 50, config.QUEUE_MAX_SLOTS]
        rows = [
            [
                b(str(v), f"qsetup:capacity:{v}")
                for v in dict.fromkeys(values)
                if v <= config.QUEUE_MAX_SLOTS
            ],
            [b("Назад", "qsetup:back:step")],
        ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def edit_setup(draft) -> None:
    if draft.message_id is not None:
        await safe_edit_text_by_id(
            bot,
            draft.chat_id,
            draft.message_id,
            setup_text(payload_of(draft), draft.step),
            setup_markup(payload_of(draft), draft.step),
        )


async def start_setup(message: Message, schedule: QueueSchedule | None = None) -> None:
    if message.from_user is None:
        return
    draft = await repository.create_draft(message.chat.id, message.from_user.id)
    payload = {"intervals": [], "weekdays": [], "kind": "weekly", "name": ""}
    step = "kind"
    if schedule is None:
        schedules = await repository.list_schedules(message.chat.id)
        if schedules:
            payload["schedules"] = [
                {"id": item.id, "name": item.name} for item in schedules
            ]
            step = "main"
    if schedule is not None:
        intervals = cast(Any, schedule).intervals
        payload = {
            "schedule_id": schedule.id,
            "kind": schedule.kind,
            "name": schedule.name,
            "once_date": schedule.once_date.isoformat() if schedule.once_date else None,
            "weekdays": schedule.weekdays or [],
            "intervals": [
                {
                    "start_minute": i.start_minute,
                    "end_minute": i.end_minute,
                    "step_minutes": i.step_minutes,
                    "capacity": i.capacity,
                    "weekdays": [i.weekday] if i.weekday is not None else [],
                }
                for i in sorted(intervals, key=lambda item: item.position)
            ],
        }
        step = "intervals"
    sent = await message.answer(
        setup_text(payload, step), reply_markup=setup_markup(payload, step)
    )
    await repository.save_draft(
        draft, step=step, payload=payload, message_id=sent.message_id
    )


@router.message(Command("q"), GroupOnly(), TeacherOnly(config.teacher_ids))
async def queue_command(message: Message, command: CommandObject) -> None:
    if (command.args or "").strip():
        await message.answer(
            "Используйте /q для настройки очередей или /qs для просмотра."
        )
        return
    await start_setup(message)


@router.message(Command("qs"), GroupOnly())
async def queues_command(message: Message) -> None:
    queues = await repository.list_queues(message.chat.id)
    await message.answer(render_queue_list(queues), reply_markup=list_markup(queues))


@router.message(F.text, GroupOnly(), TeacherOnly(config.teacher_ids))
async def setup_name(message: Message) -> None:
    draft = await repository.get_draft(message.chat.id)
    if draft is None or draft.step != "name" or not message.text:
        return
    payload = payload_of(draft)
    payload["name"] = message.text.strip()[:255] or "Очередь"
    await repository.save_draft(
        draft, step="date" if payload.get("kind") == "once" else "days", payload=payload
    )
    await edit_setup(draft)


@router.callback_query(F.data.startswith("qsetup:"), GroupOnly())
async def setup_callback(callback: CallbackQuery) -> None:
    if callback.message is None or callback.data is None:
        return
    draft = await repository.get_draft(callback.message.chat.id)
    if (
        draft is None
        or callback.from_user is None
        or callback.from_user.id != draft.teacher_id
    ):
        await safe_callback_answer(callback, "Настройка устарела.", show_alert=True)
        return
    parts, payload = callback.data.split(":"), payload_of(draft)
    action = parts[1]
    if action == "new":
        payload = {"intervals": [], "weekdays": [], "kind": "weekly", "name": ""}
        await repository.save_draft(draft, step="kind", payload=payload)
    elif action == "edit":
        schedule = await repository.get_schedule(int(parts[2]))
        if schedule is None:
            await safe_callback_answer(
                callback, "Расписание не найдено.", show_alert=True
            )
            return
        intervals = cast(Any, schedule).intervals
        payload = {
            "schedule_id": schedule.id,
            "kind": schedule.kind,
            "name": schedule.name,
            "once_date": schedule.once_date.isoformat() if schedule.once_date else None,
            "weekdays": schedule.weekdays or [],
            "intervals": [
                {
                    "start_minute": i.start_minute,
                    "end_minute": i.end_minute,
                    "step_minutes": i.step_minutes,
                    "capacity": i.capacity,
                    "weekdays": [i.weekday] if i.weekday is not None else [],
                }
                for i in sorted(intervals, key=lambda item: item.position)
            ],
        }
        await repository.save_draft(draft, step="intervals", payload=payload)
    elif action == "delete":
        await repository.delete_schedule(int(parts[2]))
        schedules = await repository.list_schedules(draft.chat_id)
        payload = {
            "schedules": [{"id": item.id, "name": item.name} for item in schedules]
        }
        await repository.save_draft(draft, step="main", payload=payload)
    elif action == "kind":
        payload["kind"] = parts[2]
        await repository.save_draft(draft, step="name", payload=payload)
    elif action == "back":
        await repository.save_draft(draft, step=parts[2], payload=payload)
    elif action == "date":
        today = datetime.now(ZoneInfo(config.QUEUE_TIMEZONE)).date()
        payload["once_date"] = today.fromordinal(
            today.toordinal() + int(parts[2])
        ).isoformat()
        await repository.save_draft(draft, step="intervals", payload=payload)
    elif action == "day":
        days = set(payload.get("weekdays") or [])
        day = int(parts[2])
        days.discard(day) if day in days else days.add(day)
        payload["weekdays"] = sorted(days)
        await repository.save_draft(draft, payload=payload)
    elif action == "days":
        if not payload.get("weekdays"):
            await safe_callback_answer(
                callback, "Выберите хотя бы один день.", show_alert=True
            )
            return
        await repository.save_draft(draft, step="intervals", payload=payload)
    elif action == "add":
        await repository.save_draft(draft, step="start", payload=payload)
    elif action == "start":
        payload["draft_start"] = int(parts[2]) * 60
        await repository.save_draft(draft, step="end", payload=payload)
    elif action == "end":
        payload["draft_end"] = int(parts[2]) * 60
        await repository.save_draft(draft, step="step", payload=payload)
    elif action == "step":
        payload["draft_step"] = (
            60 if parts[2] == "hour" else payload["draft_end"] - payload["draft_start"]
        )
        await repository.save_draft(draft, step="capacity", payload=payload)
    elif action == "capacity":
        payload.setdefault("intervals", []).append(
            {
                "start_minute": payload.pop("draft_start"),
                "end_minute": payload.pop("draft_end"),
                "step_minutes": payload.pop("draft_step"),
                "capacity": min(int(parts[2]), config.QUEUE_MAX_SLOTS),
            }
        )
        await repository.save_draft(draft, step="intervals", payload=payload)
    elif action == "remove":
        intervals = payload.get("intervals") or []
        index = int(parts[2])
        if 0 <= index < len(intervals):
            intervals.pop(index)
        await repository.save_draft(draft, step="intervals", payload=payload)
    elif action == "save":
        if not payload.get("name") or not payload.get("intervals"):
            await safe_callback_answer(
                callback, "Укажите название и добавьте интервал.", show_alert=True
            )
            return
        values: dict[str, Any] = {
            "chat_id": draft.chat_id,
            "teacher_id": draft.teacher_id,
            "name": str(payload["name"]),
            "kind": str(payload["kind"]),
            "once_date": date.fromisoformat(payload["once_date"])
            if payload.get("once_date")
            else None,
            "weekdays": [int(day) for day in payload.get("weekdays") or []],
            "timezone": config.QUEUE_TIMEZONE,
            "intervals": cast(list[dict], payload["intervals"]),
        }
        if payload.get("schedule_id"):
            await repository.update_schedule(
                payload["schedule_id"],
                name=values["name"],
                kind=values["kind"],
                once_date=values["once_date"],
                weekdays=values["weekdays"],
                timezone=values["timezone"],
                intervals=values["intervals"],
            )
        else:
            await repository.create_schedule(**values)
        await draft.delete()
        await safe_callback_answer(callback, "Сохранено.")
        await safe_edit_text_by_id(
            bot,
            callback.message.chat.id,
            callback.message.message_id,
            "<b>Очередь сохранена.</b>\n\nОткрыть расписание: /qs",
            empty_markup(),
        )
        return
    await safe_callback_answer(callback)
    await edit_setup(draft)


def render_queue(queue: Any, *, closed: bool = False) -> str:
    slots = sorted(queue.slots, key=lambda slot: slot.position)
    occupied = [slot for slot in slots if slot.user_id is not None]
    starts_at = getattr(queue, "starts_at", None)
    when = (
        starts_at.astimezone(ZoneInfo(config.QUEUE_TIMEZONE)).strftime("%d.%m %H:%M")
        if starts_at
        else ""
    )
    state = "закрыта" if closed else "активна"
    lines = [
        f"<b>{escape(getattr(queue, 'name', 'Очередь'))}</b> · {state} · {when}",
        f"Занято: {len(occupied)}/{queue.capacity}",
        "",
    ]
    lines.extend(
        f'{i}. <a href="tg://user?id={slot.user_id}">{escape(slot.user_name or str(slot.user_id))}</a>'
        for i, slot in enumerate(occupied, 1)
    )
    return "\n".join(lines or ["Пока никто не записался."])


def queue_markup(queue: Any) -> InlineKeyboardMarkup:
    slots = sorted(queue.slots, key=lambda item: item.position)
    rows = [
        [
            InlineKeyboardButton(
                text=str(slot.position),
                style="success" if slot.user_id is None else "primary",
                callback_data=f"queue:book:{queue.id}:{slot.position}"
                if slot.user_id is None
                else None,
                disabled=DisabledButton() if slot.user_id is not None else None,
            )
            for slot in slots[i : i + 5]
        ]
        for i in range(0, len(slots), 5)
    ]
    rows += [
        [
            b(
                "Освободить",
                f"queue:release:{queue.id}",
                icon=PremiumEmoji.RELEASE_SLOT.value,
            ),
            b(
                "Обновить",
                f"queue:refresh:{queue.id}",
                icon=PremiumEmoji.REFRESH_QUEUE.value,
            ),
        ],
        [b("← К списку", "qs:list")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def render_queue_list(queues: list[Queue]) -> str:
    if not queues:
        return "<b>Очереди на текущую неделю</b>\n\nОчередей нет."

    weekdays = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")

    def format_start(queue: Queue) -> str:
        if queue.starts_at is None:
            return ""
        start = queue.starts_at.astimezone(ZoneInfo(config.QUEUE_TIMEZONE))
        return f"{weekdays[start.weekday()]} {start:%d.%m %H:%M}"

    return "<b>Очереди на текущую неделю</b>\n\n" + "\n".join(
        f"• {escape(q.name)} — {format_start(q)} ({q.capacity} мест)"
        for q in queues
        if q.starts_at
    )


def list_markup(queues: list[Queue]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                b(
                    f"{q.starts_at.astimezone(ZoneInfo(config.QUEUE_TIMEZONE)):%d.%m %H:%M} · {q.name[:18]}",
                    f"qs:open:{q.id}",
                )
            ]
            for q in queues
            if q.starts_at
        ]
    )


async def stale(callback: CallbackQuery) -> None:
    await safe_callback_answer(
        callback, "Очередь уже завершена или удалена.", show_alert=True
    )
    if callback.message is not None:
        await safe_edit_text_by_id(
            bot,
            callback.message.chat.id,
            callback.message.message_id,
            "<b>Очередь завершена или удалена.</b>",
            empty_markup(),
        )


@router.callback_query(F.data.startswith("qs:"), GroupOnly())
async def queues_callback(callback: CallbackQuery) -> None:
    if callback.message is None or callback.data is None:
        return
    if callback.data == "qs:list":
        queues = await repository.list_queues(callback.message.chat.id)
        await safe_callback_answer(callback)
        await safe_edit_text_by_id(
            bot,
            callback.message.chat.id,
            callback.message.message_id,
            render_queue_list(queues),
            list_markup(queues),
        )
        return
    queue = await repository.get(int(callback.data.split(":")[2]))
    if queue is None:
        await stale(callback)
        return
    await safe_callback_answer(callback)
    await safe_edit_text_by_id(
        bot,
        callback.message.chat.id,
        callback.message.message_id,
        render_queue(queue),
        queue_markup(queue),
    )


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
    except (QueueClosedError, QueueError, ValueError):
        await stale(callback)
        return
    except AlreadyReservedError:
        await safe_callback_answer(callback, "У вас уже есть слот.", show_alert=True)
        return
    except SlotUnavailableError:
        await safe_callback_answer(callback, "Слот уже занят.", show_alert=True)
        return
    queue = await repository.get(int(queue_id))
    if queue is None:
        await stale(callback)
        return
    await safe_callback_answer(callback, "Слот занят.")
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
    queue_id = int(callback.data.split(":")[2])
    try:
        await repository.release(queue_id, callback.from_user.id)
    except NotReservedError:
        await safe_callback_answer(
            callback, "У вас нет занятого слота.", show_alert=True
        )
        return
    except (QueueClosedError, QueueError, ValueError):
        await stale(callback)
        return
    queue = await repository.get(queue_id)
    if queue is None:
        await stale(callback)
        return
    await safe_callback_answer(callback, "Слот освобождён.")
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
    queue = await repository.get(int(callback.data.split(":")[2]))
    if queue is None:
        await stale(callback)
        return
    await safe_callback_answer(callback)
    await safe_edit_text_by_id(
        bot,
        callback.message.chat.id,
        callback.message.message_id,
        render_queue(queue),
        queue_markup(queue),
    )
