from __future__ import annotations

from datetime import date, datetime
from typing import cast

from tortoise import fields, models


class QueueSchedule(models.Model):
    id = cast(int, fields.BigIntField(pk=True))
    chat_id = cast(int, fields.BigIntField())
    created_by = cast(int, fields.BigIntField())
    name = cast(str, fields.CharField(max_length=255))
    kind = cast(str, fields.CharField(max_length=16))
    once_date = cast(date | None, fields.DateField(null=True))
    weekday = cast(int | None, fields.IntField(null=True))
    start_minute = cast(int, fields.IntField())
    end_minute = cast(int, fields.IntField())
    capacity = cast(int, fields.IntField())
    timezone = cast(str, fields.CharField(max_length=64))
    enabled = cast(bool, fields.BooleanField(default=True))
    created_at = cast(datetime, fields.DatetimeField(auto_now_add=True))
    updated_at = cast(datetime, fields.DatetimeField(auto_now=True))

    class Meta:
        table = "queue_schedules"

    queues: list[Queue]


class Queue(models.Model):
    id = cast(int, fields.BigIntField(pk=True))
    schedule = cast(
        QueueSchedule | None,
        fields.ForeignKeyField(
            "models.QueueSchedule",
            related_name="queues",
            null=True,
            on_delete=fields.CASCADE,
        ),
    )
    chat_id = cast(int, fields.BigIntField())
    name = cast(str, fields.CharField(max_length=255, default="Queue"))
    message_id = cast(int | None, fields.BigIntField(null=True))
    created_by = cast(int, fields.BigIntField())
    capacity = cast(int, fields.IntField())
    starts_at = cast(datetime | None, fields.DatetimeField(null=True))
    ends_at = cast(datetime | None, fields.DatetimeField(null=True))
    occurrence_key = cast(
        str | None, fields.CharField(max_length=128, null=True, unique=True)
    )
    week_key = cast(str | None, fields.CharField(max_length=16, null=True))
    created_at = cast(datetime, fields.DatetimeField(auto_now_add=True))

    class Meta:
        table = "queues"

    slots: list[QueueSlot]


class QueueSlot(models.Model):
    id = cast(int, fields.BigIntField(pk=True))
    queue = cast(
        Queue,
        fields.ForeignKeyField(
            "models.Queue", related_name="slots", on_delete=fields.CASCADE
        ),
    )
    position = cast(int, fields.IntField())
    user_id = cast(int | None, fields.BigIntField(null=True))
    user_name = cast(str | None, fields.CharField(max_length=255, null=True))
    username = cast(str | None, fields.CharField(max_length=255, null=True))
    reserved_at = cast(datetime | None, fields.DatetimeField(null=True))

    class Meta:
        table = "queue_slots"
        unique_together = (("queue", "position"), ("queue", "user_id"))


class QueueSetupDraft(models.Model):
    id = cast(int, fields.BigIntField(pk=True))
    chat_id = cast(int, fields.BigIntField(unique=True))
    teacher_id = cast(int, fields.BigIntField())
    message_id = cast(int | None, fields.BigIntField(null=True))
    step = cast(str, fields.CharField(max_length=32))
    payload = cast(dict[str, object], fields.JSONField(default=dict))
    updated_at = cast(datetime, fields.DatetimeField(auto_now=True))

    class Meta:
        table = "queue_setup_drafts"
