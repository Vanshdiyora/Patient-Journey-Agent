from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict
class ExceptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; journey_id: UUID; journey_step_id: UUID|None; severity: str; exception_type: str; title: str; description: str; status: str; recommended_action: str|None; created_at: datetime; resolved_at: datetime|None
class ExceptionUpdate(BaseModel):
    status: str; recommended_action: str|None=None
