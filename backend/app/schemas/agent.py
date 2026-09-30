from datetime import datetime
from typing import Any
from uuid import UUID
from pydantic import BaseModel, ConfigDict
class AgentRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; journey_id: UUID; agent_name: str; run_type: str; input_context: dict[str, Any]|None; output: dict[str, Any]|None; tool_calls: list[Any]|None; status: str; started_at: datetime; completed_at: datetime|None; error_message: str|None
class OrchestrationResponse(BaseModel):
    journey_id: UUID
    status: str|None=None
    decision: dict[str, Any]|None=None
    result: dict[str, Any]|None=None
    calls: list[dict[str, Any]] = []
