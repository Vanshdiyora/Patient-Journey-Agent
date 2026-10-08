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

    # Agent-owned steps are completed only by a verified action that actually
    # fulfils them (a reminder must not complete a lab-result step).
    FULFILMENT_KEYWORDS = {
        "REQUEST_APPOINTMENT": ("APPOINTMENT", "FOLLOWUP", "SCHEDUL"),
        "RESCHEDULE_APPOINTMENT": ("APPOINTMENT", "FOLLOWUP", "SCHEDUL"),
        "REQUEST_DOCUMENT": ("LAB", "DOCUMENT", "RESULT", "AUTH", "REFERRAL"),
        "SEND_REMINDER": ("REMINDER", "NOTIF", "EDUCATION", "COMMUNICATION", "COUNSEL"),
    }

    def fulfils_step(self, action_type: str, step_type: str, step_code: str) -> bool:
        haystack = f"{step_type or ''} {step_code or ''}".upper()
        return any(k in haystack for k in self.FULFILMENT_KEYWORDS.get(action_type, ()))
