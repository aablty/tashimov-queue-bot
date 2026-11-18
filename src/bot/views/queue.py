"""Text rendering for the queue feature."""

from __future__ import annotations

from datetime import timedelta
from html import escape
from typing import Any

from src.bot.schemas.queue import QueueSchedulePayload
from src.bot.utils.emoji import PremiumEmoji
from src.bot.utils.queue import is_booking_open, local_zone, time_text, weekday_text


def setup_text(
    schedule: QueueSchedulePayload,
    step: str,
    *,
    pending_delete_bookings: int | None = None,
) -> str:
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
    if step == "edit":
        period = (
            schedule.once_date.strftime("%d.%m.%Y")
            if schedule.kind == "once" and schedule.once_date
            else weekday_text(schedule.weekday)
        )
        return (
            f"<b>{escape(schedule.name or 'Очередь')}</b>\n"
            f"Тип: {'разовая' if schedule.kind == 'once' else 'еженедельная'}\n"
            f"Период: {period}\nВремя: {time_text(schedule.start_minute, schedule.end_minute)}\n"
            f"Мест: {schedule.capacity}\n\nВыберите поле для изменения:"
        )
    if step == "delete_confirm":
        warning = (
            f"\n\n⚠️ У этой очереди есть {pending_delete_bookings} занятых мест — они пропадут."
            if pending_delete_bookings
            else "\n\nЗаписей нет, можно удалить без потерь."
        )
        return f"<b>Удалить «{escape(schedule.name or 'Очередь')}»?</b>{warning}"
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
        "time": "Настройте временной диапазон:",
        "capacity": "Выберите количество мест:",
    }.get(step, "Настройка очереди")
    return (
        "<b>Настройка очереди</b>\n\n"
        f"Название: <b>{escape(schedule.name or 'не задано')}</b>\n"
        f"Тип: <b>{kind}</b>\nПериод: <b>{period}</b>\n"
        f"Время: <b>{time_text(schedule.start_minute, schedule.end_minute)}</b>\n"
        f"Мест: <b>{schedule.capacity or 'не выбрано'}</b>\n\n{prompt}"
    )


def _booking_tip(queue: Any, *, closed: bool, occupied: int) -> str | None:
    starts_at = getattr(queue, "starts_at", None)
    ends_at = getattr(queue, "ends_at", None)
    if closed or starts_at is None or ends_at is None:
        return None
    from src.db.queue import now_utc

    now = now_utc()
    opens_at = starts_at - timedelta(minutes=10)
    if now < opens_at:
        return f"{PremiumEmoji.LAMP.html} Откроется в {opens_at.astimezone(local_zone()):%H:%M} (за 10 минут до начала)."
    if is_booking_open(starts_at, ends_at, now=now) and occupied >= queue.capacity:
        return f"{PremiumEmoji.LAMP.html} Мест нет — загляните позже, вдруг кто-то освободит слот."
    return None


def render_queue(queue: Any, *, closed: bool | None = None) -> str:
    from src.db.queue import now_utc, queue_grace_deadline

    slots = sorted(queue.slots, key=lambda slot: slot.position)
    occupied = [slot for slot in slots if slot.user_id is not None]
    starts_at = getattr(queue, "starts_at", None)
    ends_at = getattr(queue, "ends_at", None)
    if closed is None:
        closed = ends_at is not None and queue_grace_deadline(ends_at) <= now_utc()
    when = starts_at.astimezone(local_zone()).strftime("%H:%M") if starts_at else ""
    lines = [
        f"<b>{escape(getattr(queue, 'name', 'Очередь'))}</b> · {when} — занято: {len(occupied)}/{queue.capacity}",
    ]
    tip = _booking_tip(queue, closed=closed, occupied=len(occupied))
    if tip:
        lines.append(tip)
    lines.append("")
    lines.extend(
        f'{index}. <a href="tg://user?id={slot.user_id}">{escape(slot.user_name or str(slot.user_id))}</a>'
        for index, slot in enumerate(occupied, 1)
    )
    return "\n".join(lines or ["Пока никто не записался."])


def render_queue_list(queues: list[Any]) -> str:
    return (
        "<b>Очереди на текущую неделю</b>\n\nВыберите очередь:"
        if queues
        else "<b>Очереди на текущую неделю</b>\n\nОчередей нет."
    )
