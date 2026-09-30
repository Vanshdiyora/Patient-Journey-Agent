from app.action_registry.definitions import ACTION_DEFINITIONS
from app.core.exceptions import ActionNotAllowedError

class ActionRegistry:
    def list(self):
        return [
            {"action_type": d.action_type, "description": d.description, "requires_approval": d.requires_approval}
            for d in ACTION_DEFINITIONS.values()
        ]

    def get(self, action_type: str):
        return ACTION_DEFINITIONS.get(action_type)

    def validate(self, action_type: str):
        definition = self.get(action_type)
        if not definition:
            raise ActionNotAllowedError(f"Action '{action_type}' is not registered")
        return definition

    def allowed_for_step(self, step_type: str, step_code: str, blocked: bool = False):
        # Deterministic action candidates; the LLM may select only from these.
        t = (step_type or "").upper()
        code = (step_code or "").upper()
        if "APPOINTMENT" in t or "FOLLOWUP" in t or "APPOINTMENT" in code or "FOLLOWUP" in code:
            actions = ["REQUEST_APPOINTMENT", "RESCHEDULE_APPOINTMENT", "SEND_REMINDER"]
        elif "LAB" in t or "RESULT" in code or "DOCUMENT" in t or "AUTH" in code:
            actions = ["REQUEST_DOCUMENT", "SEND_REMINDER"]
        elif blocked:
            actions = ["CREATE_COORDINATOR_TASK", "SEND_REMINDER"]
        else:
            actions = ["SEND_REMINDER", "CREATE_COORDINATOR_TASK"]
        return [self.get(a) for a in actions]
