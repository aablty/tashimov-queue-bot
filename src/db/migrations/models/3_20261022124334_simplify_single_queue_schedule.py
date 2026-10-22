from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "queue_schedules" ADD "end_minute" INT NOT NULL DEFAULT 0;
        ALTER TABLE "queue_schedules" ADD "weekday" INT;
        ALTER TABLE "queue_schedules" ADD "capacity" INT NOT NULL DEFAULT 25;
        ALTER TABLE "queue_schedules" ADD "start_minute" INT NOT NULL DEFAULT 0;
        UPDATE "queue_schedules" AS schedule
        SET "weekday" = interval."weekday",
            "start_minute" = interval."start_minute",
            "end_minute" = interval."end_minute",
            "capacity" = interval."capacity"
        FROM "queue_schedule_intervals" AS interval
        WHERE interval."schedule_id" = schedule."id"
          AND interval."position" = 1;
        ALTER TABLE "queue_schedules" DROP COLUMN "weekdays";
        DROP TABLE IF EXISTS "queue_schedule_intervals";"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "queue_schedules" ADD "weekdays" JSONB NOT NULL;
        ALTER TABLE "queue_schedules" DROP COLUMN "end_minute";
        ALTER TABLE "queue_schedules" DROP COLUMN "weekday";
        ALTER TABLE "queue_schedules" DROP COLUMN "capacity";
        ALTER TABLE "queue_schedules" DROP COLUMN "start_minute";"""


MODELS_STATE = (
    "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"
    "oJiy"
)
