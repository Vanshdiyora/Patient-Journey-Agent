from typing import Any
from pydantic import BaseModel, Field

class JourneyAssessment(BaseModel):
    assessment: str
    pathway_code: str | None = None
    blocker: str | None = None
    affected_step_code: str | None = None
    reason: str
    missing_prerequisites: list[str] = Field(default_factory=list)
    contradictory_evidence: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    recommended_next_capability: str = "DETERMINISTIC"
