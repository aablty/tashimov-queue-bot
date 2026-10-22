from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from typing import Any, cast
from zoneinfo import ZoneInfo

from tortoise.exceptions import IntegrityError
from tortoise.transactions import in_transaction

from .models import (
    Queue,
    QueueSchedule,
    QueueScheduleInterval,
    QueueSetupDraft,
    QueueSlot,
)


class QueueError(Exception):
    pass


class QueueAlreadyExistsError(QueueError):
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


class QueueRepository:
    async def get_active(self, chat_id: int) -> Queue | None:
        return await Queue.filter(chat_id=chat_id).prefetch_related("slots").first()

    async def get(self, queue_id: int) -> Queue | None:
        return await Queue.filter(id=queue_id).prefetch_related("slots").first()

    async def list_schedules(self, chat_id: int) -> list[QueueSchedule]:
        return await QueueSchedule.filter(chat_id=chat_id, enabled=True).prefetch_related(
            "intervals"
        ).order_by("created_at")

    async def get_schedule(self, schedule_id: int) -> QueueSchedule | None:
        return await QueueSchedule.filter(id=schedule_id).prefetch_related(
            "intervals"
        ).first()

    async def create_draft(self, chat_id: int, teacher_id: int) -> QueueSetupDraft:
        draft, _ = await QueueSetupDraft.update_or_create(
            chat_id=chat_id,
            defaults={
                "teacher_id": teacher_id,
                "step": "kind",
                "payload": {"intervals": [], "weekdays": []},
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
        payload: dict | None = None,
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
        weekdays: list[int],
        timezone: str,
        intervals: list[dict],
    ) -> QueueSchedule:
        async with in_transaction() as connection:
            schedule = await QueueSchedule.create(
                chat_id=chat_id,
                created_by=teacher_id,
                name=name,
                kind=kind,
                once_date=once_date,
                weekdays=weekdays,
                timezone=timezone,
                using_db=connection,
            )
            position = 1
            for interval in intervals:
                interval_days = interval.get("weekdays") or ([None] if kind == "once" else weekdays)
                for weekday in interval_days:
                    await QueueScheduleInterval.create(
                        schedule=schedule,
                        position=position,
                        weekday=weekday,
                        start_minute=interval["start_minute"],
                        end_minute=interval["end_minute"],
                        step_minutes=interval.get("step_minutes", 60),
                        capacity=interval["capacity"],
                        using_db=connection,
                    )
                    position += 1
        await self.sync_schedule(schedule.id)
        result = await self.get_schedule(schedule.id)
        if result is None:
            raise QueueError
        return result

    async def update_schedule(self, schedule_id: int, **values: object) -> QueueSchedule:
        schedule = await self.get_schedule(schedule_id)
        if schedule is None:
            raise QueueError
        intervals = cast(list[dict[str, Any]], values.pop("intervals"))
        async with in_transaction() as connection:
            await Queue.filter(schedule_id=schedule.id).using_db(connection).delete()
            await QueueScheduleInterval.filter(schedule_id=schedule.id).using_db(connection).delete()
            for key, value in values.items():
                setattr(schedule, key, value)
            await schedule.save(using_db=connection)
            position = 1
            for interval in intervals:
                interval_days = interval.get("weekdays") or (
                    [None] if schedule.kind == "once" else schedule.weekdays
                )
                for weekday in interval_days:
                    await QueueScheduleInterval.create(
                        schedule=schedule,
                        position=position,
                        weekday=weekday,
                        start_minute=interval["start_minute"],
                        end_minute=interval["end_minute"],
                        step_minutes=interval.get("step_minutes", 60),
                        capacity=interval["capacity"],
                        using_db=connection,
                    )
                    position += 1
        await self.sync_schedule(schedule.id)
        result = await self.get_schedule(schedule.id)
        if result is None:
            raise QueueError
        return result

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
        once_schedule_ids = cast(
            list[int], await QueueSchedule.filter(kind="once").values_list("id", flat=True)
        )
        if once_schedule_ids:
            await Queue.filter(
                ends_at__lte=now_utc(), schedule_id__in=once_schedule_ids
            ).delete()

    async def sync_schedule(self, schedule_id: int) -> None:
        schedule = await self.get_schedule(schedule_id)
        if schedule is None or not schedule.enabled:
            return
        timezone = ZoneInfo(schedule.timezone)
        current = datetime.now(timezone)
        if schedule.kind == "once":
            if schedule.once_date is None:
                return
            targets = [schedule.once_date]
        else:
            monday = current.date() - timedelta(days=current.weekday())
            targets = [monday + timedelta(days=offset) for offset in range(7)]
        intervals = sorted(cast(Any, schedule).intervals, key=lambda item: item.position)
        for interval in intervals:
            for target in targets:
                if schedule.kind == "weekly" and interval.weekday != target.weekday():
                    continue
                cursor = interval.start_minute
                while cursor < interval.end_minute:
                    end_minute = min(cursor + interval.step_minutes, interval.end_minute)
                    starts_at = local_datetime(target, cursor, schedule.timezone)
                    ends_at = local_datetime(target, end_minute, schedule.timezone)
                    occurrence = (
                        f"{schedule.id}:{interval.id}:{cursor}"
                        if schedule.kind == "weekly"
                        else f"{schedule.id}:{interval.id}:{target.isoformat()}:{cursor}"
                    )
                    existing = await Queue.filter(occurrence_key=occurrence).first()
                    if existing is None:
                        try:
                            await self._create_occurrence(
                                schedule,
                                interval,
                                occurrence,
                                starts_at,
                                ends_at,
                                week_key(target) if schedule.kind == "weekly" else None,
                            )
                        except IntegrityError:
                            pass
                    elif schedule.kind == "weekly":
                        await self._refresh_weekly_occurrence(
                            existing, starts_at, ends_at, week_key(target), interval.capacity
                        )
                    cursor = end_minute

    async def _create_occurrence(
        self,
        schedule: QueueSchedule,
        interval: QueueScheduleInterval,
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
                capacity=interval.capacity,
                starts_at=starts_at,
                ends_at=ends_at,
                occurrence_key=occurrence,
                week_key=current_week,
                using_db=connection,
            )
            await QueueSlot.bulk_create(
                [QueueSlot(queue=queue, position=i) for i in range(1, interval.capacity + 1)],
                using_db=connection,
            )
        return queue

    async def _refresh_weekly_occurrence(
        self,
        queue: Queue,
        starts_at: datetime,
        ends_at: datetime,
        current_week: str,
        capacity: int,
    ) -> None:
        if queue.week_key != current_week:
            await QueueSlot.filter(queue_id=queue.id).update(
                user_id=None,
                user_name=None,
                username=None,
                reserved_at=None,
            )
            queue.week_key = current_week
        queue.starts_at = starts_at
        queue.ends_at = ends_at
        if queue.capacity != capacity:
            await QueueSlot.filter(queue_id=queue.id, position__gt=capacity).delete()
            current_count = await QueueSlot.filter(queue_id=queue.id).count()
            if current_count < capacity:
                await QueueSlot.bulk_create(
                    [QueueSlot(queue=queue, position=i) for i in range(current_count + 1, capacity + 1)]
                )
            queue.capacity = capacity
        await queue.save(update_fields=("week_key", "starts_at", "ends_at", "capacity"))

    async def list_queues(self, chat_id: int) -> list[Queue]:
        await self.sync_all(chat_id)
        return await Queue.filter(
            chat_id=chat_id, ends_at__gt=now_utc()
        ).prefetch_related("slots").order_by("starts_at")

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
            if queue is None or (queue.ends_at is not None and queue.ends_at <= now_utc()):
                raise QueueClosedError
            existing = await QueueSlot.filter(queue_id=queue_id, user_id=user_id).using_db(connection).first()
            if existing is not None:
                raise AlreadyReservedError
            slot = await QueueSlot.filter(queue_id=queue_id, position=position).using_db(connection).select_for_update().first()
            if slot is None or slot.user_id is not None:
                raise SlotUnavailableError
            slot.user_id = user_id
            slot.user_name = name
            slot.username = username
            slot.reserved_at = now_utc()
            await slot.save(using_db=connection)
            return slot

    async def release(self, queue_id: int, user_id: int) -> QueueSlot:
        async with in_transaction() as connection:
            queue = await Queue.filter(id=queue_id).using_db(connection).first()
            if queue is None or (queue.ends_at is not None and queue.ends_at <= now_utc()):
                raise QueueClosedError
            slot = await QueueSlot.filter(queue_id=queue_id, user_id=user_id).using_db(connection).select_for_update().first()
            if slot is None:
                raise NotReservedError
            slot.user_id = None
            slot.user_name = None
            slot.username = None
            slot.reserved_at = None
            await slot.save(using_db=connection)
            return slot
