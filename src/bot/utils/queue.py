"""Shared queue formatting, timezone and ordering helpers."""

from __future__ import annotations

from typing import Any
from zoneinfo import ZoneInfo

from src.bot.schemas.queue import ScheduleSummary
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


def summary_sort_key(item: ScheduleSummary) -> tuple[int, int, str]:
    period = (
        item.once_date.toordinal()
        if item.kind == "once" and item.once_date is not None
        else item.weekday
        if item.weekday is not None
        else 999999
    )
    return period, item.start_minute, item.name.casefold()


def queue_sort_key(queue: Any) -> tuple[object, int, str]:
    starts_at = queue.starts_at.astimezone(local_zone())
    return (
        starts_at.date(),
        starts_at.hour * 60 + starts_at.minute,
        queue.name.casefold(),
    )
