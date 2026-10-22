from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from aiogram.types import DisabledButton, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.bot.schemas.queue import QueueSchedulePayload, ScheduleSummary
from src.bot.utils.emoji import PremiumEmoji
from src.bot.utils.queue import (
    WEEKDAYS,
    local_zone,
    minimum_start_minute,
    queue_sort_key,
    summary_period,
    summary_sort_key,
    time_text,
    weekday_text,
)
from src.core.config import config


def markup(buttons: list[InlineKeyboardButton], *widths: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.add(*buttons)
    builder.adjust(*widths)
    return builder.as_markup()


def cancel_setup_button() -> InlineKeyboardButton:
    return InlineKeyboardButton(
        text="Отмена",
        callback_data="qsetup:cancel",
        icon_custom_emoji_id=PremiumEmoji.TAG_CROSS.value or None,
    )


def setup_markup(
    schedule: QueueSchedulePayload,
    step: str,
    summaries: list[ScheduleSummary] | None = None,
) -> InlineKeyboardMarkup:
    edit_menu = schedule.schedule_id is not None
    if step == "main":
        return markup(
            [
                InlineKeyboardButton(
                    text="Новая очередь",
                    callback_data="qsetup:new",
                    icon_custom_emoji_id=PremiumEmoji.PLUS.value,
                ),
                *[
                    InlineKeyboardButton(
                        text=f"{item.name[:20]} · {summary_period(item)} {time_text(item.start_minute, item.end_minute)}",
                        callback_data=f"qsetup:edit:{item.id}",
                    )
                    for item in sorted(summaries or [], key=summary_sort_key)
                ],
            ],
            1,
        )
    if step == "review":
        return markup(
            [
                InlineKeyboardButton(
                    text="Изменить",
                    callback_data=f"qsetup:editform:{schedule.schedule_id}",
                    icon_custom_emoji_id=PremiumEmoji.BRUSH.value,
                ),
                InlineKeyboardButton(
                    text="Удалить",
                    callback_data=f"qsetup:delete:{schedule.schedule_id}",
                    icon_custom_emoji_id=PremiumEmoji.TRASH.value,
                ),
                InlineKeyboardButton(
                    text="Отмена",
                    callback_data="qsetup:cancel",
                    icon_custom_emoji_id=PremiumEmoji.TAG_CROSS.value,
                ),
            ],
            1,
        )
    if step == "edit":
        return markup(
            [
                InlineKeyboardButton(
                    text="Название", callback_data="qsetup:field:name"
                ),
                InlineKeyboardButton(text="Тип", callback_data="qsetup:field:kind"),
                InlineKeyboardButton(
                    text="Период", callback_data="qsetup:field:period"
                ),
                InlineKeyboardButton(text="Время", callback_data="qsetup:field:time"),
                InlineKeyboardButton(
                    text="Места", callback_data="qsetup:field:capacity"
                ),
                InlineKeyboardButton(
                    text="Сохранить",
                    callback_data="qsetup:save",
                    icon_custom_emoji_id=PremiumEmoji.SAVE.value,
                ),
                InlineKeyboardButton(
                    text="Назад",
                    callback_data="qsetup:review",
                    icon_custom_emoji_id=PremiumEmoji.ARROW_LEFT.value,
                ),
                cancel_setup_button(),
            ],
            2,
            3,
            1,
            2,
        )
    if step == "kind":
        return markup(
            [
                InlineKeyboardButton(
                    text="Разовая",
                    callback_data="qsetup:kind:once",
                    icon_custom_emoji_id=PremiumEmoji.DOT.value,
                ),
                InlineKeyboardButton(
                    text="Еженедельная",
                    callback_data="qsetup:kind:weekly",
                    icon_custom_emoji_id=PremiumEmoji.CALENDAR.value,
                ),
                cancel_setup_button(),
            ],
            2,
            1,
        )
    if step == "name":
        return markup(
            [
                InlineKeyboardButton(
                    text="Назад",
                    callback_data="qsetup:editmenu"
                    if edit_menu
                    else "qsetup:back:kind",
                    icon_custom_emoji_id=PremiumEmoji.ARROW_LEFT.value,
                ),
                cancel_setup_button(),
            ],
            2,
        )
    if step == "date":
        now = datetime.now(local_zone()).date()
        return markup(
            [
                InlineKeyboardButton(
                    text="‹",
                    callback_data="qsetup:date:prev",
                    disabled=DisabledButton()
                    if schedule.once_date is None or schedule.once_date <= now
                    else None,
                ),
                InlineKeyboardButton(
                    text=(schedule.once_date or now).strftime("%d.%m.%Y"),
                    disabled=DisabledButton(),
                ),
                InlineKeyboardButton(text="›", callback_data="qsetup:date:next"),
                InlineKeyboardButton(
                    text="Назад",
                    callback_data="qsetup:editmenu"
                    if edit_menu
                    else "qsetup:back:name",
                    icon_custom_emoji_id=PremiumEmoji.ARROW_LEFT.value,
                ),
                InlineKeyboardButton(
                    text="Готово",
                    callback_data="qsetup:date:done",
                    icon_custom_emoji_id=PremiumEmoji.CHECKMARK.value,
                ),
                cancel_setup_button(),
            ],
            3,
            2,
            1
        )
    if step == "day":
        return markup(
            [
                *[
                    InlineKeyboardButton(
                        text=label, callback_data=f"qsetup:day:{index}"
                    )
                    for index, label in enumerate(WEEKDAYS)
                ],
                InlineKeyboardButton(
                    text="Назад",
                    callback_data="qsetup:editmenu"
                    if edit_menu
                    else "qsetup:back:name",
                    icon_custom_emoji_id=PremiumEmoji.ARROW_LEFT.value,
                ),
                cancel_setup_button(),
            ],
            3,
            3,
            2,
        )
    if step == "start":
        return markup(
            [
                *[
                    InlineKeyboardButton(
                        text=f"{hour:02d}:00", callback_data=f"qsetup:start:{hour}"
                    )
                    for hour in range(24)
                ],
                InlineKeyboardButton(
                    text="Назад",
                    callback_data="qsetup:editmenu"
                    if edit_menu
                    else "qsetup:back:period",
                    icon_custom_emoji_id=PremiumEmoji.ARROW_LEFT.value,
                ),
                cancel_setup_button(),
            ],
            *([3] * 8),
            2,
        )
    if step == "time":
        start = schedule.start_minute if schedule.start_minute is not None else 9 * 60
        end = schedule.end_minute if schedule.end_minute is not None else start + 60
        minimum_start = (
            minimum_start_minute(schedule.once_date)
            if schedule.once_date is not None
            else 0
        )
        return markup(
            [
                InlineKeyboardButton(
                    text="↑",
                    callback_data="qsetup:time:start:up",
                    disabled=DisabledButton()
                    if start + 120 > end or start >= 23 * 60
                    else None,
                ),
                InlineKeyboardButton(
                    text="↑",
                    callback_data="qsetup:time:end:up",
                    disabled=DisabledButton() if end >= 23 * 60 + 59 else None,
                ),
                InlineKeyboardButton(
                    text=f"{start // 60:02d}:{start % 60:02d}",
                    disabled=DisabledButton(),
                ),
                InlineKeyboardButton(
                    text=f"{end // 60:02d}:{end % 60:02d}",
                    disabled=DisabledButton(),
                ),
                InlineKeyboardButton(
                    text="↓",
                    callback_data="qsetup:time:start:down",
                    disabled=DisabledButton() if start <= minimum_start else None,
                ),
                InlineKeyboardButton(
                    text="↓",
                    callback_data="qsetup:time:end:down",
                    disabled=DisabledButton() if end - 120 < start else None,
                ),
                InlineKeyboardButton(
                    text="Назад",
                    callback_data="qsetup:editmenu"
                    if edit_menu
                    else "qsetup:back:period",
                    icon_custom_emoji_id=PremiumEmoji.ARROW_LEFT.value,
                ),
                InlineKeyboardButton(
                    text="Готово",
                    callback_data="qsetup:time:done",
                    icon_custom_emoji_id=PremiumEmoji.CHECKMARK.value,
                ),
                cancel_setup_button(),
            ],
            2,
            2,
            2,
            2,
            1
        )
    if step == "end":
        first = (schedule.start_minute or 0) // 60 + 1
        count = 24 - first
        widths = [3] * (count // 3)
        if count % 3:
            widths.append(count % 3)
        widths.append(2)
        return markup(
            [
                *[
                    InlineKeyboardButton(
                        text=f"{hour:02d}:00", callback_data=f"qsetup:end:{hour}"
                    )
                    for hour in range(first, 24)
                ],
                InlineKeyboardButton(
                    text="Назад",
                    callback_data="qsetup:back:start",
                    icon_custom_emoji_id=PremiumEmoji.ARROW_LEFT.value,
                ),
                cancel_setup_button(),
            ],
            *widths,
        )
    values = [15, 25, 50, config.QUEUE_MAX_SLOTS]
    return markup(
        [
            *[
                InlineKeyboardButton(
                    text=str(value), callback_data=f"qsetup:capacity:{value}"
                )
                for value in dict.fromkeys(values)
                if value <= config.QUEUE_MAX_SLOTS
            ],
            InlineKeyboardButton(
                text="Назад",
                callback_data="qsetup:back:end",
                icon_custom_emoji_id=PremiumEmoji.ARROW_LEFT.value,
            ),
            cancel_setup_button(),
        ],
        4,
        2,
    )


def queue_markup(queue: Any) -> InlineKeyboardMarkup:
    from src.db.queue import queue_grace_deadline

    ends_at = getattr(queue, "ends_at", None)
    if ends_at is not None and queue_grace_deadline(ends_at) <= datetime.now(UTC):
        return markup([])
    slots = sorted(queue.slots, key=lambda item: item.position)
    slot_buttons = [
        InlineKeyboardButton(
            text=str(slot.position),
            style="success" if slot.user_id is None else "primary",
            callback_data=f"queue:book:{queue.id}:{slot.position}"
            if slot.user_id is None
            else None,
            disabled=DisabledButton() if slot.user_id is not None else None,
        )
        for slot in slots
    ]
    action_buttons = [
        InlineKeyboardButton(
            text="Освободить",
            callback_data=f"queue:release:{queue.id}",
            icon_custom_emoji_id=PremiumEmoji.ERASER.value,
        ),
        InlineKeyboardButton(
            text="Обновить",
            callback_data=f"queue:refresh:{queue.id}",
            icon_custom_emoji_id=PremiumEmoji.REFRESH.value,
        ),
        InlineKeyboardButton(
            text="К списку",
            callback_data="qs:list",
            icon_custom_emoji_id=PremiumEmoji.ARROW_LEFT.value,
        ),
    ]
    slot_builder = InlineKeyboardBuilder()
    slot_builder.add(*slot_buttons)
    slot_builder.adjust(5)
    action_builder = InlineKeyboardBuilder()
    action_builder.add(*action_buttons)
    action_builder.adjust(2, 1)
    slot_builder.attach(action_builder)
    return slot_builder.as_markup()


def list_markup(queues: list[Any]) -> InlineKeyboardMarkup:
    return markup(
        [
            InlineKeyboardButton(
                text=f"{queue.name[:24]} · {weekday_text(queue.starts_at.astimezone(local_zone()).weekday())} {queue.starts_at.astimezone(local_zone()):%H:%M}",
                callback_data=f"qs:open:{queue.id}",
            )
            for queue in sorted(queues, key=queue_sort_key)
            if queue.starts_at
        ],
        1,
    )
