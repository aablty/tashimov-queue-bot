from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        DELETE FROM "queues" WHERE "status" = 'closed';
        DROP INDEX IF EXISTS "uid_queues_active__2eca99";
        ALTER TABLE "queues" DROP COLUMN "closed_at";
        ALTER TABLE "queues" DROP COLUMN "status";
        ALTER TABLE "queues" DROP COLUMN "active_key";
        CREATE UNIQUE INDEX IF NOT EXISTS "uid_queues_chat_id_013718" ON "queues" ("chat_id");"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "queues" DROP CONSTRAINT IF EXISTS "queues_chat_id_key";
        DROP INDEX IF EXISTS "uid_queues_chat_id_013718";
        ALTER TABLE "queues" ADD "closed_at" TIMESTAMPTZ;
        ALTER TABLE "queues" ADD "status" VARCHAR(16) NOT NULL DEFAULT 'active';
        ALTER TABLE "queues" ADD "active_key" BIGINT UNIQUE;"""


MODELS_STATE = (
    "eJztmVtT2kAUx78Kkyc7Yx0MILRvEbFSK7SSaTs6zs6SLGHHZIPJRmUs3727m/sNDbUOIG"
    "9w9py9/M4J57/hSbJsHZnuwQ8PeUj6XHuSCLT4h/TAfk2Cs1ls5gYKx6bwvOMuwgTHLnWg"
    "Rpl1Ak0XMZOOXM3BM4ptwqzEM01utDXmiIkRmzyC2TyA2gaiU+SwgesbZsZER49s8uDr7B"
    "ZMMDL11E6xztcWdkDnM2E7xkaf0FPhyxccA802PYvE/rM5ndokCsCEcquBCHIgRXwF6nj8"
    "BHyDwVHDQ/mbjV38XSZidDSBnkkTJx6D2CYBMBiqYNRTAZAqMNJswvmyrboCgMG38PGTLD"
    "cabbneOOq0mu12q1PvMF+x3/xQe+FvJqblTyWY9b/0ByrfkM2S6OeWGxYiBlLoR4lkxPS1"
    "KaSgagoSQc/nIaS+SwSLSTygyHWhgSqzT8ethD+AG9EPXWL88eO/tfw1B3FCYDyvWPupuN"
    "cp//eZADiDGqYF+MvZJ0K2ibx82Gw3O42jZgQ8sizjXF7UkOapnrARii20vKz9yAxcPQg9"
    "CD9sImp2QH1IzHnwA7iEq9q/6I1U5eI7X85y3TtT8FPUHh+RhXWese4dfUgXfDRJ7VdfPa"
    "vxr7Wr4aAn8NouNRyxYuynXkl8T9CjNiD2A4B6ohGG1pDagsupyW2ipXPDGGq3D9DRQWok"
    "Lg/XtKlb8HMXhJ2eXyITCrD5GkgKyhGbZwNLYBEWfWgNS4Gzs2W7jGZ+yJKtrAUS1pX1YG"
    "2+Ug5YmTwPaT4j0UGUvdfV6df+9EFdYjEFO1HC7LnI4XrjZifp16eRlkv6KIsvb6zJkF1j"
    "LWis4SNQqawTQTudvqpMFBDFlxz77hQ6S8iHQRn27EgbyN6Cj8BExKBTXsSt1hKuP5XL7p"
    "lyuce8MppkEAzJ/lge9Cqcd5grYWayDzn3K2n0TOgriPQ1w78hmjxkkhPlyTz7mq1qy0hG"
    "bVMjfoOmkbsRZXKRT8Sp7SBskHM0F8nos41DohX9mGXfpm9YEsouPszswIdIwKeqj52enR"
    "lRvwMoo65y0pMW5bfM/3mHUpCDtalUcIEKRvaX3Z5g7LM2f3C8l6vQPwrw8kvOPXLcwjtO"
    "uVhJhKykVdbtqX4DscIfqgqEA/ctpHtYr7+ALvMqpSvGMm9rbUIRKZCBX0fDQclr2jgkK/"
    "+wRmt/aiZ2N1EmLIHLYaREX8h070L5ncXd/TY8zqo5PsFxkUB4y2a2+AsZ9AIP"
)
