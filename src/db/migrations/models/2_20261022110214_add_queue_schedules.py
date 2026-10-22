from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "queues" DROP CONSTRAINT IF EXISTS "queues_chat_id_key";
        DROP INDEX IF EXISTS "uid_queues_chat_id_013718";
        CREATE TABLE IF NOT EXISTS "queue_schedules" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "chat_id" BIGINT NOT NULL,
    "created_by" BIGINT NOT NULL,
    "name" VARCHAR(255) NOT NULL,
    "kind" VARCHAR(16) NOT NULL,
    "once_date" DATE,
    "weekdays" JSONB NOT NULL,
    "timezone" VARCHAR(64) NOT NULL,
    "enabled" BOOL NOT NULL,
    "created_at" TIMESTAMPTZ NOT NULL,
    "updated_at" TIMESTAMPTZ NOT NULL
);
        CREATE TABLE IF NOT EXISTS "queue_setup_drafts" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "chat_id" BIGINT NOT NULL UNIQUE,
    "teacher_id" BIGINT NOT NULL,
    "message_id" BIGINT,
    "step" VARCHAR(32) NOT NULL,
    "payload" JSONB NOT NULL,
    "updated_at" TIMESTAMPTZ NOT NULL
);
        CREATE TABLE IF NOT EXISTS "queue_schedule_intervals" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "position" INT NOT NULL,
    "weekday" INT,
    "start_minute" INT NOT NULL,
    "end_minute" INT NOT NULL,
    "step_minutes" INT NOT NULL,
    "capacity" INT NOT NULL,
    "schedule_id" BIGINT NOT NULL REFERENCES "queue_schedules" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_queue_sched_schedul_d851c3" UNIQUE ("schedule_id", "position")
);
        ALTER TABLE "queues" ADD "schedule_id" BIGINT;
        ALTER TABLE "queues" ADD "week_key" VARCHAR(16);
        ALTER TABLE "queues" ADD "starts_at" TIMESTAMPTZ;
        ALTER TABLE "queues" ADD "occurrence_key" VARCHAR(128) UNIQUE;
        ALTER TABLE "queues" ADD "ends_at" TIMESTAMPTZ;
        ALTER TABLE "queues" ADD "name" VARCHAR(255) NOT NULL DEFAULT 'Queue';
        ALTER TABLE "queues" ADD CONSTRAINT "fk_queues_queue_sc_33e1b237" FOREIGN KEY ("schedule_id") REFERENCES "queue_schedules" ("id") ON DELETE CASCADE;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP INDEX IF EXISTS "uid_queues_occurre_afb4e2";
        ALTER TABLE "queues" DROP CONSTRAINT IF EXISTS "fk_queues_queue_sc_33e1b237";
        ALTER TABLE "queues" DROP COLUMN "schedule_id";
        ALTER TABLE "queues" DROP COLUMN "week_key";
        ALTER TABLE "queues" DROP COLUMN "starts_at";
        ALTER TABLE "queues" DROP COLUMN "occurrence_key";
        ALTER TABLE "queues" DROP COLUMN "ends_at";
        ALTER TABLE "queues" DROP COLUMN "name";
        DROP TABLE IF EXISTS "queue_schedules";
        DROP TABLE IF EXISTS "queue_schedule_intervals";
        DROP TABLE IF EXISTS "queue_setup_drafts";
        CREATE UNIQUE INDEX IF NOT EXISTS "uid_queues_chat_id_013718" ON "queues" ("chat_id");"""


MODELS_STATE = (
    "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"
    "md/OaOCDEoJv/wN2xT3z"
)
