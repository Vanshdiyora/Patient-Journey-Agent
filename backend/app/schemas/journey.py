from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict
class JourneyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; patient_id: UUID; pathway_id: UUID; pathway_version: int; status: str; priority: str; started_at: datetime; target_completion_at: datetime|None=None; completed_at: datetime|None=None; created_at: datetime|None=None; updated_at: datetime|None=None
class JourneyStepResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; journey_id: UUID; pathway_step_id: UUID; status: str; due_at: datetime|None=None; started_at: datetime|None=None; completed_at: datetime|None=None; block_reason: str|None=None; last_evaluated_at: datetime|None=None
