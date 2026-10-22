"""Text rendering for the queue feature."""

from __future__ import annotations

from html import escape
from typing import Any

from src.bot.schemas.queue import QueueSchedulePayload
from src.bot.utils.queue import local_zone, time_text, weekday_text


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


def render_queue_list(queues: list[Any]) -> str:
    return (
        "<b>Очереди на текущую неделю</b>\n\nВыберите очередь:"
        if queues
        else "<b>Очереди на текущую неделю</b>\n\nОчередей нет."
    )
