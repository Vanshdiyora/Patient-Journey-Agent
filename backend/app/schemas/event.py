from datetime import datetime
from typing import Any
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
class EventCreate(BaseModel):
    event_type: str = Field(min_length=1, max_length=100)
    source: str = Field(min_length=1, max_length=100)
    external_event_id: str|None=None
    event_time: datetime
    payload: dict[str, Any] = Field(default_factory=dict)
class EventResponse(EventCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; patient_id: UUID; journey_id: UUID; processed: bool; created_at: datetime|None=None
