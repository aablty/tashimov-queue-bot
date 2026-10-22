from tortoise import fields, models


class QueueSchedule(models.Model):
    id = fields.BigIntField(pk=True)
    chat_id = fields.BigIntField()
    created_by = fields.BigIntField()
    name = fields.CharField(max_length=255)
    kind = fields.CharField(max_length=16)
    once_date = fields.DateField(null=True)
    weekdays = fields.JSONField(default=list)
    timezone = fields.CharField(max_length=64)
    enabled = fields.BooleanField(default=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "queue_schedules"


class QueueScheduleInterval(models.Model):
    id = fields.BigIntField(pk=True)
    schedule = fields.ForeignKeyField(
        "models.QueueSchedule", related_name="intervals", on_delete=fields.CASCADE
    )
    position = fields.IntField()
    weekday = fields.IntField(null=True)
    start_minute = fields.IntField()
    end_minute = fields.IntField()
    step_minutes = fields.IntField(default=60)
    capacity = fields.IntField()

    class Meta:
        table = "queue_schedule_intervals"
        unique_together = (("schedule", "position"),)


class Queue(models.Model):
    id = fields.BigIntField(pk=True)
    schedule = fields.ForeignKeyField(
        "models.QueueSchedule", related_name="queues", null=True, on_delete=fields.CASCADE
    )
    chat_id = fields.BigIntField()
    name = fields.CharField(max_length=255, default="Queue")
    message_id = fields.BigIntField(null=True)
    created_by = fields.BigIntField()
    capacity = fields.IntField()
    starts_at = fields.DatetimeField(null=True)
    ends_at = fields.DatetimeField(null=True)
    occurrence_key = fields.CharField(max_length=128, null=True, unique=True)
    week_key = fields.CharField(max_length=16, null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "queues"


class QueueSlot(models.Model):
    id = fields.BigIntField(pk=True)
    queue = fields.ForeignKeyField(
        "models.Queue", related_name="slots", on_delete=fields.CASCADE
    )
    position = fields.IntField()
    user_id = fields.BigIntField(null=True)
    user_name = fields.CharField(max_length=255, null=True)
    username = fields.CharField(max_length=255, null=True)
    reserved_at = fields.DatetimeField(null=True)

    class Meta:
        table = "queue_slots"
        unique_together = (("queue", "position"), ("queue", "user_id"))


class QueueSetupDraft(models.Model):
    id = fields.BigIntField(pk=True)
    chat_id = fields.BigIntField(unique=True)
    teacher_id = fields.BigIntField()
    message_id = fields.BigIntField(null=True)
    step = fields.CharField(max_length=32)
    payload = fields.JSONField(default=dict)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "queue_setup_drafts"
