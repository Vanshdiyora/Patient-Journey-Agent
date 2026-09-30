from typing import Any
from pydantic import BaseModel, Field

class CoordinationDecision(BaseModel):
    action_type: str
    reason: str
    payload: dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.0
