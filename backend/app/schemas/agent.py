from datetime import datetime
from typing import Any
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
class AgentRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; journey_id: UUID; agent_name: str; run_type: str; input_context: dict[str, Any]|None; output: dict[str, Any]|None; tool_calls: list[Any]|None; status: str; started_at: datetime; completed_at: datetime|None; error_message: str|None
class OrchestrationResponse(BaseModel):
    journey_id: UUID
    run_id: UUID|None=None
    status: str|None=None
    decision: dict[str, Any]|None=None
    result: dict[str, Any]|None=None
    outcomes: list[dict[str, Any]] = Field(default_factory=list)
    calls: list[dict[str, Any]] = Field(default_factory=list)
    summary: str | None = None
    mode: str | None = None
    warnings: list[str] = Field(default_factory=list)
    step_changes: list[dict[str, Any]] = Field(default_factory=list)
    journey_status: dict[str, Any] | None = None
