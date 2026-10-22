from __future__ import annotations

from datetime import UTC, datetime
from html import escape
from typing import Any
from zoneinfo import ZoneInfo

from aiogram.types import DisabledButton, InlineKeyboardButton, InlineKeyboardMarkup

from src.bot.queue_payloads import QueueSchedulePayload, ScheduleSummary
from src.bot.utils.emoji import PremiumEmoji
from src.core.config import config

WEEKDAYS = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб")


def local_zone() -> ZoneInfo:
    return ZoneInfo(config.QUEUE_TIMEZONE)


def time_text(start: int | None, end: int | None) -> str:
    if start is None or end is None:
        return "не выбрано"
    return f"{start // 60:02d}:{start % 60:02d}–{end // 60:02d}:{end % 60:02d}"


def weekday_text(value: int | None) -> str:
    return (
        WEEKDAYS[value]
        if value is not None and 0 <= value < len(WEEKDAYS)
        else "не выбран"
    )


def summary_period(item: ScheduleSummary) -> str:
    if item.kind == "once" and item.once_date is not None:
        return item.once_date.strftime("%d.%m")
    return weekday_text(item.weekday)


def setup_text(schedule: QueueSchedulePayload, step: str) -> str:
    if step == "main":
        return "<b>Расписания группы</b>\n\nВыберите очередь для редактирования или создайте новую."
    if step == "review":
        period = (
            schedule.once_date.strftime("%d.%m.%Y")
            if schedule.kind == "once" and schedule.once_date
            else weekday_text(schedule.weekday)
        )
        return (
            f"<b>{escape(schedule.name or 'Очередь')}</b>\n"
            f"Тип: {'разовая' if schedule.kind == 'once' else 'еженедельная'}\n"
            f"Период: {period}\nВремя: {time_text(schedule.start_minute, schedule.end_minute)}\n"
            f"Мест: {schedule.capacity}\n\nВыберите действие:"
        )
    kind = "разовая" if schedule.kind == "once" else "еженедельная"
    period = (
        schedule.once_date.strftime("%d.%m.%Y")
        if schedule.kind == "once" and schedule.once_date
        else weekday_text(schedule.weekday)
    )
    prompt = {
        "kind": "Выберите тип очереди:",
        "name": "Отправьте название очереди следующим сообщением.",
        "date": "Выберите дату:",
        "day": "Выберите день недели:",
        "start": "Выберите начало:",
        "end": "Выберите конец:",
        "capacity": "Выберите количество мест:",
    }.get(step, "Настройка очереди")
    return (
        "<b>Настройка очереди</b>\n\n"
        f"Название: <b>{escape(schedule.name or 'не задано')}</b>\n"
        f"Тип: <b>{kind}</b>\nПериод: <b>{period}</b>\n"
        f"Время: <b>{time_text(schedule.start_minute, schedule.end_minute)}</b>\n"
        f"Мест: <b>{schedule.capacity or 'не выбрано'}</b>\n\n{prompt}"
    )


def setup_markup(
    schedule: QueueSchedulePayload,
    step: str,
    summaries: list[ScheduleSummary] | None = None,
) -> InlineKeyboardMarkup:
    if step == "main":
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Новая очередь",
                        callback_data="qsetup:new",
                        icon_custom_emoji_id=PremiumEmoji.ADD_QUEUE.value or None,
                    )
                ],
                *[
                    [
                        InlineKeyboardButton(
                            text=f"{item.name[:20]} · {summary_period(item)} {time_text(item.start_minute, item.end_minute)}",
                            callback_data=f"qsetup:edit:{item.id}",
                        )
                    ]
                    for item in summaries or []
                ],
            ]
        )
    if step == "kind":
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Разовая", callback_data="qsetup:kind:once"
                    ),
                    InlineKeyboardButton(
                        text="Еженедельная", callback_data="qsetup:kind:weekly"
                    ),
                ]
            ]
        )
    if step == "name":
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Назад",
                        callback_data="qsetup:back:kind",
                        icon_custom_emoji_id=PremiumEmoji.BACK.value or None,
                    )
                ]
            ]
        )
    if step == "date":
        now = datetime.now(local_zone()).date()
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=now.fromordinal(now.toordinal() + index).strftime("%d.%m"),
                        callback_data=f"qsetup:date:{index}",
                    )
                    for index in range(7)
                ],
                [
                    InlineKeyboardButton(
                        text="Назад",
                        callback_data="qsetup:back:name",
                        icon_custom_emoji_id=PremiumEmoji.BACK.value or None,
                    )
                ],
            ]
        )
    if step == "day":
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=label, callback_data=f"qsetup:day:{index}"
                    )
                    for index, label in enumerate(WEEKDAYS)
                ],
                [
                    InlineKeyboardButton(
                        text="Назад",
                        callback_data="qsetup:back:name",
                        icon_custom_emoji_id=PremiumEmoji.BACK.value or None,
                    )
                ],
            ]
        )
    if step == "start":
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=f"{hour:02d}:00", callback_data=f"qsetup:start:{hour}"
                    )
                    for hour in range(12)
                ],
                [
                    InlineKeyboardButton(
                        text=f"{hour:02d}:00", callback_data=f"qsetup:start:{hour}"
                    )
                    for hour in range(12, 24)
                ],
                [
                    InlineKeyboardButton(
                        text="Назад",
                        callback_data="qsetup:back:period",
                        icon_custom_emoji_id=PremiumEmoji.BACK.value or None,
                    )
                ],
            ]
        )
    if step == "end":
        first = (schedule.start_minute or 0) // 60 + 1
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=f"{hour:02d}:00", callback_data=f"qsetup:end:{hour}"
                    )
                    for hour in range(first, 12)
                ],
                [
                    InlineKeyboardButton(
                        text=f"{hour:02d}:00", callback_data=f"qsetup:end:{hour}"
                    )
                    for hour in range(max(12, first), 24)
                ],
                [
                    InlineKeyboardButton(
                        text="Назад",
                        callback_data="qsetup:back:start",
                        icon_custom_emoji_id=PremiumEmoji.BACK.value or None,
                    )
                ],
            ]
        )
    values = [1, 5, 10, 15, 20, 25, 50, config.QUEUE_MAX_SLOTS]
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=str(value), callback_data=f"qsetup:capacity:{value}"
                )
                for value in dict.fromkeys(values)
                if value <= config.QUEUE_MAX_SLOTS
            ],
            [
                InlineKeyboardButton(
                    text="Назад",
                    callback_data="qsetup:back:end",
                    icon_custom_emoji_id=PremiumEmoji.BACK.value or None,
                )
            ],
        ]
    )


def render_queue(queue: Any, *, closed: bool = False) -> str:
    slots = sorted(queue.slots, key=lambda slot: slot.position)
    occupied = [slot for slot in slots if slot.user_id is not None]
    starts_at = getattr(queue, "starts_at", None)
    when = starts_at.astimezone(local_zone()).strftime("%H:%M") if starts_at else ""
    state = "закрыта" if closed else "активна"
    lines = [
        f"<b>{escape(getattr(queue, 'name', 'Очередь'))}</b> · {state} · {when}",
        f"Занято: {len(occupied)}/{queue.capacity}",
        "",
    ]
    lines.extend(
        f'{index}. <a href="tg://user?id={slot.user_id}">{escape(slot.user_name or str(slot.user_id))}</a>'
        for index, slot in enumerate(occupied, 1)
    )
    return "\n".join(lines or ["Пока никто не записался."])


def queue_markup(queue: Any) -> InlineKeyboardMarkup:
    from src.db.queue import queue_grace_deadline

    ends_at = getattr(queue, "ends_at", None)
    if ends_at is not None and queue_grace_deadline(ends_at) <= datetime.now(UTC):
        return InlineKeyboardMarkup(inline_keyboard=[])
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
            for slot in slots[index : index + 5]
        ]
        for index in range(0, len(slots), 5)
    ]
    rows += [
        [
            InlineKeyboardButton(
                text="Освободить",
                callback_data=f"queue:release:{queue.id}",
                icon_custom_emoji_id=PremiumEmoji.RELEASE_SLOT.value or None,
            ),
            InlineKeyboardButton(
                text="Обновить",
                callback_data=f"queue:refresh:{queue.id}",
                icon_custom_emoji_id=PremiumEmoji.REFRESH_QUEUE.value or None,
            ),
        ],
        [
            InlineKeyboardButton(
                text="К списку",
                callback_data="qs:list",
                icon_custom_emoji_id=PremiumEmoji.BACK.value or None,
            )
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def render_queue_list(queues: list[Any]) -> str:
    return (
        "<b>Очереди на текущую неделю</b>\n\nВыберите очередь:"
        if queues
        else "<b>Очереди на текущую неделю</b>\n\nОчередей нет."
    )


def list_markup(queues: list[Any]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{queue.name[:24]} · {weekday_text(queue.starts_at.astimezone(local_zone()).weekday())} {queue.starts_at.astimezone(local_zone()):%H:%M}",
                    callback_data=f"qs:open:{queue.id}",
                )
            ]
            for queue in queues
            if queue.starts_at
        ]
    )
