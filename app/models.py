from datetime import datetime
from typing import Annotated, Self

from pydantic import (
    AwareDatetime,
    BaseModel,
    StringConstraints,
    field_validator,
    model_validator,
)


class Calendar(BaseModel):
    id: str
    title: str
    time_zone: str


class Event(BaseModel):
    id: str
    title: str
    start_time: datetime
    end_time: datetime


class CreateEventRequest(BaseModel):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    start_time: AwareDatetime
    end_time: AwareDatetime

    @field_validator("start_time", "end_time", mode="before")
    @classmethod
    def require_datetime_string(cls, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("Time must be an ISO 8601 datetime string")
        datetime.fromisoformat(value)
        return value

    @model_validator(mode="after")
    def validate_time_order(self) -> Self:
        if self.end_time <= self.start_time:
            raise ValueError("End time must be after start time")
        return self
