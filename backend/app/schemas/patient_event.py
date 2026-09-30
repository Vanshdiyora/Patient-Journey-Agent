"""
Patient-safe event schema: only fields a patient may legitimately supply.
The server sets source/actor/verified; anything that could influence journey
state (verified, step_completed, status) is deliberately absent.
"""
from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

# Event types a patient may submit. Everything else is rejected.
PATIENT_EVENT_TYPES = {
    "SYMPTOM_REPORTED",
    "APPOINTMENT_PREFERENCE",
    "DOCUMENT_UPLOADED",
    "GENERAL_UPDATE",
    "QUESTION_ASKED",
}

# Allowed payload keys (anything else is stripped server-side).
PATIENT_PAYLOAD_KEYS = {"comment", "preference", "document_name", "severity_self_reported", "notes"}


class PatientEventCreate(BaseModel):
    event_type: Literal[*PATIENT_EVENT_TYPES] = Field(min_length=1, max_length=100)
    payload: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(json_schema_extra={
        "example": {"event_type": "SYMPTOM_REPORTED", "payload": {"comment": "Feeling better today"}}
    })


class PatientEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    event_type: str
    source: str
    event_time: datetime
    payload: dict[str, Any]
    processed: bool
    created_at: datetime | None = None


class PatientProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    patient_reference: str
    first_name: str
    last_name: str
    email: str | None = None
    date_of_birth: date | None = None
    gender: str | None = None
