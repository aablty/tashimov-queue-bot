from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from typing import Any, cast
from zoneinfo import ZoneInfo

from tortoise.exceptions import IntegrityError
from tortoise.transactions import in_transaction

from src.core.config import config

from .models import Queue, QueueSchedule, QueueSetupDraft, QueueSlot


class QueueError(Exception):
    pass


class QueueClosedError(QueueError):
    pass


class SlotUnavailableError(QueueError):
    pass


class AlreadyReservedError(QueueError):
    pass


class NotReservedError(QueueError):
    pass


def week_key(day: date) -> str:
    iso = day.isocalendar()
    return f"{iso.year}-{iso.week:02d}"


def local_datetime(day: date, minute: int, timezone: str) -> datetime:
    return datetime.combine(day, time(minute // 60, minute % 60), ZoneInfo(timezone))


def now_utc() -> datetime:
    return datetime.now(UTC)


def queue_grace_deadline(ends_at: datetime) -> datetime:
    return ends_at + timedelta(minutes=config.QUEUE_GRACE_MINUTES)


class QueueRepository:
    async def get(self, queue_id: int) -> Queue | None:
        return await Queue.filter(id=queue_id).prefetch_related("slots").first()

    async def list_schedules(self, chat_id: int) -> list[QueueSchedule]:
        return await QueueSchedule.filter(chat_id=chat_id, enabled=True).order_by(
            "created_at"
        )

    async def get_schedule(self, schedule_id: int) -> QueueSchedule | None:
        return await QueueSchedule.get_or_none(id=schedule_id)

    async def create_draft(self, chat_id: int, teacher_id: int) -> QueueSetupDraft:
        draft, _ = await QueueSetupDraft.update_or_create(
            chat_id=chat_id,
            defaults={
                "teacher_id": teacher_id,
                "step": "kind",
                "payload": {"kind": "weekly", "name": ""},
                "message_id": None,
            },
        )
        return draft

    async def get_draft(self, chat_id: int) -> QueueSetupDraft | None:
        return await QueueSetupDraft.get_or_none(chat_id=chat_id)

    async def save_draft(
        self,
        draft: QueueSetupDraft,
        *,
        step: str | None = None,
        payload: dict[str, Any] | None = None,
        message_id: int | None = None,
    ) -> QueueSetupDraft:
        if step is not None:
            draft.step = step
        if payload is not None:
            draft.payload = payload
        if message_id is not None:
            draft.message_id = message_id
        await draft.save()
        return draft

    async def create_schedule(
        self,
        *,
        chat_id: int,
        teacher_id: int,
        name: str,
        kind: str,
        once_date: date | None,
        weekday: int | None,
        start_minute: int,
        end_minute: int,
        capacity: int,
        timezone: str,
    ) -> QueueSchedule:
        schedule = await QueueSchedule.create(
            chat_id=chat_id,
            created_by=teacher_id,
            name=name,
            kind=kind,
            once_date=once_date,
            weekday=weekday,
            start_minute=start_minute,
            end_minute=end_minute,
            capacity=capacity,
            timezone=timezone,
        )
        await self.sync_schedule(schedule.id)
        return schedule

    async def update_schedule(
        self, schedule_id: int, **values: object
    ) -> QueueSchedule:
        schedule = await self.get_schedule(schedule_id)
        if schedule is None:
            raise QueueError
        await Queue.filter(schedule_id=schedule.id).delete()
        for key, value in values.items():
            setattr(schedule, key, value)
        await schedule.save()
        await self.sync_schedule(schedule.id)
        return schedule

    async def delete_schedule(self, schedule_id: int) -> None:
        schedule = await QueueSchedule.get_or_none(id=schedule_id)
        if schedule is not None:
            await schedule.delete()

    async def sync_all(self, chat_id: int | None = None) -> None:
        await self.cleanup_expired()
        query = QueueSchedule.filter(enabled=True)
        if chat_id is not None:
            query = query.filter(chat_id=chat_id)
        schedule_ids = cast(list[int], await query.values_list("id", flat=True))
        for schedule_id in schedule_ids:
            await self.sync_schedule(schedule_id)

    async def cleanup_expired(self) -> None:
        for schedule in await QueueSchedule.filter(kind="once", enabled=True):
            if schedule.once_date is None:
                continue
            expires_at = local_datetime(
                schedule.once_date, schedule.end_minute, schedule.timezone
            )
            if queue_grace_deadline(expires_at) <= now_utc():
                await schedule.delete()

    async def sync_schedule(self, schedule_id: int) -> None:
        schedule = await self.get_schedule(schedule_id)
        if schedule is None or not schedule.enabled:
            return
        timezone = ZoneInfo(schedule.timezone)
        current = datetime.now(timezone)
        if schedule.kind == "once":
            if schedule.once_date is None:
                return
            target = schedule.once_date
            current_week = None
            occurrence = f"{schedule.id}:{target.isoformat()}"
        else:
            if schedule.weekday is None or not 0 <= schedule.weekday <= 5:
                return
            monday = current.date() - timedelta(days=current.weekday())
            target = monday + timedelta(days=schedule.weekday)
            current_week = week_key(target)
            occurrence = f"{schedule.id}:{current_week}"
        starts_at = local_datetime(target, schedule.start_minute, schedule.timezone)
        ends_at = local_datetime(target, schedule.end_minute, schedule.timezone)
        existing = await Queue.filter(occurrence_key=occurrence).first()
        if existing is None:
            try:
                await self._create_occurrence(
                    schedule, occurrence, starts_at, ends_at, current_week
                )
            except IntegrityError:
                return
        elif schedule.kind == "weekly" and current_week is not None:
            await self._refresh_weekly_occurrence(
                existing, starts_at, ends_at, current_week
            )

    async def _create_occurrence(
        self,
        schedule: QueueSchedule,
        occurrence: str,
        starts_at: datetime,
        ends_at: datetime,
        current_week: str | None,
    ) -> Queue:
        async with in_transaction() as connection:
            queue = await Queue.create(
                schedule=schedule,
                chat_id=schedule.chat_id,
                name=schedule.name,
                created_by=schedule.created_by,
                capacity=schedule.capacity,
                starts_at=starts_at,
                ends_at=ends_at,
                occurrence_key=occurrence,
                week_key=current_week,
                using_db=connection,
            )
            await QueueSlot.bulk_create(
                [
                    QueueSlot(queue=queue, position=i)
                    for i in range(1, schedule.capacity + 1)
                ],
                using_db=connection,
            )
        return queue

    async def _refresh_weekly_occurrence(
        self, queue: Queue, starts_at: datetime, ends_at: datetime, current_week: str
    ) -> None:
        if queue.week_key != current_week:
            await QueueSlot.filter(queue_id=queue.id).update(
                user_id=None, user_name=None, username=None, reserved_at=None
            )
            queue.week_key = current_week
        queue.starts_at = starts_at
        queue.ends_at = ends_at
        await queue.save(update_fields=("week_key", "starts_at", "ends_at"))

    async def list_queues(self, chat_id: int) -> list[Queue]:
        await self.sync_all(chat_id)
        return (
            await Queue.filter(chat_id=chat_id, ends_at__gt=now_utc())
            .prefetch_related("slots")
            .order_by("starts_at")
        )

    async def reserve(
        self,
        queue_id: int,
        position: int,
        user_id: int,
        name: str,
        username: str | None,
    ) -> QueueSlot:
        async with in_transaction() as connection:
            queue = await Queue.filter(id=queue_id).using_db(connection).first()
            if queue is None or (
                queue.ends_at is not None
                and queue_grace_deadline(queue.ends_at) <= now_utc()
            ):
                raise QueueClosedError
            existing = (
                await QueueSlot.filter(queue_id=queue_id, user_id=user_id)
                .using_db(connection)
                .select_for_update()
                .first()
            )
            if existing is not None and existing.position == position:
                raise AlreadyReservedError
            if existing is not None:
                existing.user_id = existing.user_name = existing.username = (
                    existing.reserved_at
                ) = None
                await existing.save(using_db=connection)
            slot = (
                await QueueSlot.filter(queue_id=queue_id, position=position)
                .using_db(connection)
                .select_for_update()
                .first()
            )
            if slot is None or slot.user_id is not None:
                raise SlotUnavailableError
            slot.user_id, slot.user_name, slot.username, slot.reserved_at = (
                user_id,
                name,
                username,
                now_utc(),
            )
            await slot.save(using_db=connection)
            return slot

    async def release(self, queue_id: int, user_id: int) -> QueueSlot:
        async with in_transaction() as connection:
            queue = await Queue.filter(id=queue_id).using_db(connection).first()
            if queue is None or (
                queue.ends_at is not None
                and queue_grace_deadline(queue.ends_at) <= now_utc()
            ):
                raise QueueClosedError
            slot = (
                await QueueSlot.filter(queue_id=queue_id, user_id=user_id)
                .using_db(connection)
                .select_for_update()
                .first()
            )
            if slot is None:
                raise NotReservedError
            slot.user_id = slot.user_name = slot.username = slot.reserved_at = None
            await slot.save(using_db=connection)
            return slot
