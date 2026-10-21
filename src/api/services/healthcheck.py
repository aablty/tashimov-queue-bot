from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from aiogram.exceptions import TelegramAPIError
from pydantic import BaseModel
from tortoise import get_connection
from tortoise.exceptions import BaseORMException

from src.bot import bot


class Health(BaseModel):
    healthy: bool
    data: dict | None = None

    @classmethod
    def ok(cls, data: Any = None) -> "Health":
        return cls(healthy=True, data=data)

    @classmethod
    def error(cls, data: Any = None) -> "Health":
        return cls(healthy=False, data=data)

    def to_dict(self, details: bool = False) -> dict:
        return self.model_dump() if details else {"healthy": self.healthy}


class HealthcheckService:
    async def health_handler(self, details: bool = False) -> tuple[dict, bool]:
        db_health = await self.check_db()
        bot_health = await self.check_bot()

        healthy = all([db_health.healthy, bot_health.healthy])

        data = {
            "status": "healthy" if healthy else "unhealthy",
            "timestamp": datetime.now(UTC).isoformat(),
            "checks": {
                "db": db_health.to_dict(details),
                "bot": bot_health.to_dict(details),
            },
        }

        return data, healthy

    async def check_db(self) -> Health:
        try:
            conn = get_connection("default")

            start = perf_counter()
            _, rows = await conn.execute_query(
                query=(
                    "SELECT "
                    "version() AS version, "
                    "pg_size_pretty(pg_database_size(current_database())) AS db_size, "
                    "pg_postmaster_start_time() AS started_at;"
                )
            )
            latency = round((perf_counter() - start) * 1000, 2)

            info = rows[0]
            uptime = datetime.now(UTC) - info["started_at"]

            return Health.ok(
                data={
                    **info,
                    "started_at": info["started_at"].isoformat(),
                    "uptime_seconds": int(uptime.total_seconds()),
                    "latency_ms": latency,
                }
            )

        except BaseORMException as e:
            return Health.error(data={"error": str(e)})

    async def check_bot(self) -> Health:
        try:
            me = await bot.get_me()
            webhook_info = await bot.get_webhook_info()

            return Health.ok(
                data={
                    **me.model_dump(
                        include={
                            "id",
                            "username",
                        }
                    ),
                    **webhook_info.model_dump(
                        include={
                            "pending_update_count",
                            "last_error_date",
                            "last_error_message",
                            "last_synchronization_error_date",
                        }
                    ),
                }
            )

        except TelegramAPIError as e:
            return Health.error(data={"error": str(e)})
