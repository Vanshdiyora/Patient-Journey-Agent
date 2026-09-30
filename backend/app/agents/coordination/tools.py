from app.action_registry.registry import ActionRegistry
registry = ActionRegistry()

def allowed_actions(step_type: str, step_code: str, blocked: bool):
    return [d.action_type for d in registry.allowed_for_step(step_type, step_code, blocked)]
