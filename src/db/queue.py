from datetime import UTC, datetime

from tortoise.exceptions import IntegrityError
from tortoise.transactions import in_transaction

from .models import Queue, QueueSlot


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


class QueueRepository:
    async def create(self, chat_id: int, teacher_id: int, capacity: int) -> Queue:
        try:
            async with in_transaction() as connection:
                queue = await Queue.create(
                    chat_id=chat_id,
                    created_by=teacher_id,
                    capacity=capacity,
                    active_key=chat_id,
                    using_db=connection,
                )
                await QueueSlot.bulk_create(
                    [
                        QueueSlot(queue=queue, position=position)
                        for position in range(1, capacity + 1)
                    ],
                    using_db=connection,
                )
        except IntegrityError as exc:
            raise QueueAlreadyExistsError from exc
        return queue

    async def get_active(self, chat_id: int) -> Queue | None:
        return (
            await Queue.filter(chat_id=chat_id, status="active")
            .prefetch_related("slots")
            .first()
        )

    async def get(self, queue_id: int) -> Queue | None:
        return await Queue.filter(id=queue_id).prefetch_related("slots").first()

    async def close(self, queue_id: int) -> Queue:
        queue = await Queue.get_or_none(id=queue_id)
        if queue is None:
            raise QueueError
        if queue.status == "active":
            queue.status = "closed"
            queue.active_key = None
            queue.closed_at = datetime.now(UTC)
            await queue.save(update_fields=("status", "active_key", "closed_at"))
        return queue

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
            if queue is None or queue.status != "active":
                raise QueueClosedError
            existing = (
                await QueueSlot.filter(queue_id=queue_id, user_id=user_id)
                .using_db(connection)
                .first()
            )
            if existing is not None:
                raise AlreadyReservedError
            slot = (
                await QueueSlot.filter(queue_id=queue_id, position=position)
                .using_db(connection)
                .select_for_update()
                .first()
            )
            if slot is None or slot.user_id is not None:
                raise SlotUnavailableError
            slot.user_id = user_id
            slot.user_name = name
            slot.username = username
            slot.reserved_at = datetime.now(UTC)
            await slot.save(using_db=connection)
            return slot

    async def release(self, queue_id: int, user_id: int) -> QueueSlot:
        async with in_transaction() as connection:
            queue = await Queue.filter(id=queue_id).using_db(connection).first()
            if queue is None or queue.status != "active":
                raise QueueClosedError
            slot = (
                await QueueSlot.filter(queue_id=queue_id, user_id=user_id)
                .using_db(connection)
                .select_for_update()
                .first()
            )
            if slot is None:
                raise NotReservedError
            slot.user_id = None
            slot.user_name = None
            slot.username = None
            slot.reserved_at = None
            await slot.save(using_db=connection)
            return slot
