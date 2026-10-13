from datetime import date
from uuid import UUID
from pydantic import BaseModel, ConfigDict
class PatientResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; patient_reference: str; first_name: str; last_name: str; email: str | None = None; date_of_birth: date; gender: str; assigned_clinician_id: UUID | None = None; assigned_clinician_name: str | None = None
