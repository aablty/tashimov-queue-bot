from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, cast

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, Message

from src.bot import bot
from src.bot.filters import GroupOnly, TeacherOnly
from src.bot.queue_payloads import (
    QueueDraftPayload,
    QueueSchedulePayload,
    ScheduleSummary,
)
from src.bot.queue_ui import (
    list_markup,
    local_zone,
    queue_markup,
    render_queue,
    render_queue_list,
    setup_markup,
    setup_text,
)
from src.bot.utils.telegram import (
    safe_callback_answer,
    safe_delete,
    safe_edit_text_by_id,
)
from src.core.config import config
from src.db.models import QueueSchedule
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


def draft_payload(draft: Any) -> QueueDraftPayload:
    raw = dict(draft.payload or {})
    if "schedule" not in raw:
        schedule = {
            key: raw[key] for key in QueueSchedulePayload.model_fields if key in raw
        }
        raw = {"schedule": schedule, "schedules": raw.get("schedules", [])}
    return QueueDraftPayload.model_validate(raw)


def schedule_summary(schedule: QueueSchedule) -> ScheduleSummary:
    kind = cast(Literal["once", "weekly"], schedule.kind)
    return ScheduleSummary(
        id=schedule.id,
        name=schedule.name,
        kind=kind,
        once_date=schedule.once_date,
        weekday=schedule.weekday
        if schedule.weekday is not None and 0 <= schedule.weekday <= 5
        else None,
        start_minute=schedule.start_minute,
        end_minute=schedule.end_minute,
        capacity=schedule.capacity,
    )


async def edit_setup(draft: Any) -> None:
    if draft.message_id is None:
        return
    payload = draft_payload(draft)
    await safe_edit_text_by_id(
        bot,
        draft.chat_id,
        draft.message_id,
        setup_text(payload.schedule, draft.step),
        setup_markup(payload.schedule, draft.step, payload.schedules),
    )


async def start_setup(message: Message) -> None:
    if message.from_user is None:
        return
    draft = await repository.create_draft(message.chat.id, message.from_user.id)
    schedules = await repository.list_schedules(message.chat.id)
    payload = QueueDraftPayload(
        schedule=QueueSchedulePayload(),
        schedules=[schedule_summary(schedule) for schedule in schedules],
    )
    step = "main" if schedules else "kind"
    sent = await message.answer(
        setup_text(payload.schedule, step),
        reply_markup=setup_markup(payload.schedule, step, payload.schedules),
    )
    await repository.save_draft(
        draft,
        step=step,
        payload=payload.model_dump(mode="json"),
        message_id=sent.message_id,
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
    if (
        draft is None
        or draft.step != "name"
        or not message.text
        or message.text.startswith("/")
    ):
        return
    payload = draft_payload(draft)
    payload.schedule.name = message.text.strip()[:255] or "Очередь"
    next_step = (
        "edit"
        if payload.schedule.schedule_id is not None
        else ("date" if payload.schedule.kind == "once" else "day")
    )
    await repository.save_draft(
        draft, step=next_step, payload=payload.model_dump(mode="json")
    )
    await edit_setup(draft)
    await safe_delete(message)


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
    payload = draft_payload(draft)
    parts = callback.data.split(":")
    action = parts[1]
    schedule = payload.schedule

    if action in {"main", "cancel"}:
        schedules = await repository.list_schedules(draft.chat_id)
        payload = QueueDraftPayload(
            schedules=[
                schedule_summary(item)
                for item in schedules
                if item.kind == "once"
                or (item.weekday is not None and 0 <= item.weekday <= 5)
            ]
        )
        await repository.save_draft(
            draft, step="main", payload=payload.model_dump(mode="json")
        )
    elif action == "new":
        await repository.save_draft(
            draft, step="kind", payload=QueueDraftPayload().model_dump(mode="json")
        )
    elif action in {"edit", "editform"}:
        selected = await repository.get_schedule(int(parts[2]))
        if selected is None:
            await safe_callback_answer(callback, "Очередь удалена.", show_alert=True)
            return
        selected_payload = QueueSchedulePayload(
            schedule_id=selected.id,
            kind=cast(Literal["once", "weekly"], selected.kind),
            name=selected.name,
            once_date=selected.once_date,
            weekday=selected.weekday,
            start_minute=selected.start_minute,
            end_minute=selected.end_minute,
            capacity=selected.capacity,
        )
        await repository.save_draft(
            draft,
            step="review" if action == "edit" else "edit",
            payload=QueueDraftPayload(schedule=selected_payload).model_dump(
                mode="json"
            ),
        )
    elif action == "review":
        await repository.save_draft(
            draft, step="review", payload=payload.model_dump(mode="json")
        )
    elif action == "editmenu":
        await repository.save_draft(
            draft, step="edit", payload=payload.model_dump(mode="json")
        )
    elif action == "field":
        field = parts[2]
        if field == "name":
            target = "name"
        elif field == "kind":
            target = "kind"
        elif field == "period":
            target = "date" if schedule.kind == "once" else "day"
        elif field == "time":
            target = "start"
        elif field == "capacity":
            target = "capacity"
        else:
            await safe_callback_answer(callback, "Неизвестное поле.", show_alert=True)
            return
        await repository.save_draft(
            draft, step=target, payload=payload.model_dump(mode="json")
        )
    elif action == "delete":
        await repository.delete_schedule(int(parts[2]))
        schedules = await repository.list_schedules(draft.chat_id)
        payload = QueueDraftPayload(
            schedules=[
                schedule_summary(item)
                for item in schedules
                if item.kind == "once"
                or (item.weekday is not None and 0 <= item.weekday <= 5)
            ]
        )
        await repository.save_draft(
            draft, step="main", payload=payload.model_dump(mode="json")
        )
    elif action == "kind":
        new_kind = cast(Literal["once", "weekly"], parts[2])
        if new_kind != schedule.kind:
            schedule.once_date = None
            schedule.weekday = None
        schedule.kind = new_kind
        next_step = "edit" if schedule.schedule_id is not None else "name"
        await repository.save_draft(
            draft, step=next_step, payload=payload.model_dump(mode="json")
        )
    elif action == "back":
        target = parts[2]
        if target == "period":
            target = "date" if schedule.kind == "once" else "day"
        await repository.save_draft(
            draft, step=target, payload=payload.model_dump(mode="json")
        )
    elif action == "date":
        today = datetime.now(local_zone()).date()
        schedule.once_date = today.fromordinal(today.toordinal() + int(parts[2]))
        next_step = "edit" if schedule.schedule_id is not None else "start"
        await repository.save_draft(
            draft, step=next_step, payload=payload.model_dump(mode="json")
        )
    elif action == "day":
        schedule.weekday = int(parts[2])
        next_step = "edit" if schedule.schedule_id is not None else "start"
        await repository.save_draft(
            draft, step=next_step, payload=payload.model_dump(mode="json")
        )
    elif action == "start":
        schedule.start_minute = int(parts[2]) * 60
        await repository.save_draft(
            draft, step="end", payload=payload.model_dump(mode="json")
        )
    elif action == "end":
        schedule.end_minute = int(parts[2]) * 60
        next_step = "edit" if schedule.schedule_id is not None else "capacity"
        await repository.save_draft(
            draft, step=next_step, payload=payload.model_dump(mode="json")
        )
    elif action == "save":
        if not schedule.is_complete():
            await safe_callback_answer(
                callback, "Заполните все поля очереди.", show_alert=True
            )
            return
        values = schedule.model_dump(exclude={"schedule_id"})
        if schedule.schedule_id is None:
            await repository.create_schedule(
                chat_id=draft.chat_id,
                teacher_id=draft.teacher_id,
                timezone=config.QUEUE_TIMEZONE,
                **values,
            )
        else:
            await repository.update_schedule(schedule.schedule_id, **values)
        await draft.delete()
        await safe_callback_answer(callback, "Сохранено.")
        await safe_edit_text_by_id(
            bot,
            callback.message.chat.id,
            callback.message.message_id,
            "<b>Очередь сохранена.</b>\n\nОткрыть очереди: /qs",
            None,
        )
        return
    elif action == "capacity":
        schedule.capacity = min(int(parts[2]), config.QUEUE_MAX_SLOTS)
        if schedule.schedule_id is not None:
            await repository.save_draft(
                draft, step="edit", payload=payload.model_dump(mode="json")
            )
            await safe_callback_answer(callback)
            await edit_setup(draft)
            return
        if not schedule.is_complete():
            await safe_callback_answer(
                callback, "Заполните все поля очереди.", show_alert=True
            )
            return
        values = schedule.model_dump(exclude={"schedule_id"})
        if schedule.schedule_id is None:
            await repository.create_schedule(
                chat_id=draft.chat_id,
                teacher_id=draft.teacher_id,
                timezone=config.QUEUE_TIMEZONE,
                **values,
            )
        else:
            await repository.update_schedule(schedule.schedule_id, **values)
        await draft.delete()
        await safe_callback_answer(callback, "Сохранено.")
        await safe_edit_text_by_id(
            bot,
            callback.message.chat.id,
            callback.message.message_id,
            "<b>Очередь сохранена.</b>\n\nОткрыть очереди: /qs",
            None,
        )
        return
    await safe_callback_answer(
        callback,
        "Настройка отменена." if action == "cancel" else None,
    )
    await edit_setup(draft)


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
            None,
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
    except AlreadyReservedError:
        await safe_callback_answer(
            callback, "У вас уже есть этот слот.", show_alert=True
        )
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
