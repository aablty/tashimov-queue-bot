from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class QueueSchedulePayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    schedule_id: int | None = None
    kind: Literal["once", "weekly"] = "weekly"
    name: str = ""
    once_date: date | None = None
    weekday: int | None = Field(default=None, ge=0, le=5)
    start_minute: int | None = Field(default=None, ge=0, le=1439)
    end_minute: int | None = Field(default=None, ge=1, le=1440)
    capacity: int | None = Field(default=None, ge=1)

    def has_time(self) -> bool:
        return self.start_minute is not None and self.end_minute is not None

    def is_complete(self) -> bool:
        return bool(
            self.name.strip()
            and self.has_time()
            and self.capacity is not None
            and (
                (self.kind == "once" and self.once_date is not None)
                or (self.kind == "weekly" and self.weekday is not None)
            )
        )


class ScheduleSummary(BaseModel):
    id: int
    name: str
    kind: Literal["once", "weekly"]
    once_date: date | None = None
    weekday: int | None = None
    start_minute: int
    end_minute: int
    capacity: int


class QueueDraftPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    schedule: QueueSchedulePayload = Field(default_factory=QueueSchedulePayload)
    schedules: list[ScheduleSummary] = Field(default_factory=list)
