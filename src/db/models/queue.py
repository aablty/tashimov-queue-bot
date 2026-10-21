from tortoise import fields, models


class Queue(models.Model):
    id = fields.BigIntField(pk=True)
    chat_id = fields.BigIntField(unique=True)
    message_id = fields.BigIntField(null=True)
    created_by = fields.BigIntField()
    capacity = fields.IntField()
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
