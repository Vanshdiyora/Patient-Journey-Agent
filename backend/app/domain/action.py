from dataclasses import dataclass
from typing import Any

@dataclass
class ActionRequest:
    action_type: str
    journey_id: str
    journey_step_id: str | None
    payload: dict[str, Any]
    reason: str
    requires_approval: bool = False
