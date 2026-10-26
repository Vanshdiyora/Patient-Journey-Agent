from datetime import timedelta, timezone
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator


class CalendarConfirmation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=0)
    confirmed: bool

    @field_validator("confirmed")
    @classmethod
    def require_confirmation(cls, value):
        if not value:
            raise ValueError("Scheduling confirmation is required")
        return value


class CalendarBooking(CalendarConfirmation):
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    assigned_staff_id: UUID | None = None

    @model_validator(mode="after")
    def validate_interval(self):
        self.starts_at = self.starts_at.astimezone(timezone.utc)
        self.ends_at = self.ends_at.astimezone(timezone.utc)
        if self.ends_at <= self.starts_at:
            raise ValueError("End time must be after start time")
        if self.ends_at - self.starts_at > timedelta(days=7):
            raise ValueError("An activity cannot span more than seven days")
        return self


class CalendarCreate(CalendarBooking):
    journey_step_id: UUID
