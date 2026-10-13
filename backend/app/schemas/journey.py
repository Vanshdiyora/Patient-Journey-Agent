from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Literal

class JourneyCreate(BaseModel):
    pathway_id: UUID
    priority: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"] | None = None
    step_time_limits_hours: dict[UUID, int] = Field(default_factory=dict)

    @field_validator("step_time_limits_hours")
    @classmethod
    def validate_time_limits(cls, values):
        if any(value < 1 or value > 8760 for value in values.values()):
            raise ValueError("Step time limits must be between 1 and 8760 hours")
        return values


class JourneyPriorityUpdate(BaseModel):
    priority: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]


class JourneyStepTimeLimitUpdate(BaseModel):
    time_limit_hours: int = Field(ge=1, le=8760)


class JourneyStepComplete(BaseModel):
    confirmed: bool

    @field_validator("confirmed")
    @classmethod
    def require_confirmation(cls, value: bool) -> bool:
        if not value:
            raise ValueError("Staff confirmation is required")
        return value


class JourneyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; patient_id: UUID; pathway_id: UUID; pathway_version: int; status: str; priority: str; started_at: datetime; target_completion_at: datetime|None=None; completed_at: datetime|None=None; created_at: datetime|None=None; updated_at: datetime|None=None; pathway_name: str|None=None
class JourneyStepResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; journey_id: UUID; pathway_step_id: UUID; status: str; owner_role: str|None=None; time_limit_hours: int|None=None; due_at: datetime|None=None; planned_due_at: datetime|None=None; due_after_days: int|None=None; started_at: datetime|None=None; completed_at: datetime|None=None; block_reason: str|None=None; last_evaluated_at: datetime|None=None; name: str|None=None; description: str|None=None; sequence_number: int|None=None; patient_submission_pending: bool=False
