from typing import Any
from app.action_registry.registry import ActionRegistry

registry = ActionRegistry()

def validate_agent_action(action: dict[str, Any], allowed_types: list[str] | None = None):
    action_type = action.get("action_type")
    definition = registry.validate(action_type)
    if allowed_types is not None and action_type not in allowed_types:
        raise ValueError(f"Action '{action_type}' is not allowed for the current step")
    payload = action.get("payload") or {}
    return {"action_type": definition.action_type, "payload": payload, "requires_approval": definition.requires_approval}
