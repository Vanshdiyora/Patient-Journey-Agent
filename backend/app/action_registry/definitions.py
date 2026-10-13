from dataclasses import dataclass
from typing import Any, Callable

@dataclass(frozen=True)
class ActionDefinition:
    action_type: str
    description: str
    requires_approval: bool
    handler_name: str
    agent_may_self_approve: bool = False

ACTION_DEFINITIONS = {
    "REQUEST_DOCUMENT": ActionDefinition("REQUEST_DOCUMENT", "Request a missing diagnostic/report/document.", False, "request_document"),
    "SEND_REMINDER": ActionDefinition("SEND_REMINDER", "Send an operational reminder/notification.", False, "send_reminder"),
    "REQUEST_APPOINTMENT": ActionDefinition("REQUEST_APPOINTMENT", "Submit a scheduling request.", False, "request_appointment"),
    "RESCHEDULE_APPOINTMENT": ActionDefinition("RESCHEDULE_APPOINTMENT", "Submit a rescheduling request when allowed.", False, "reschedule_appointment"),
    "CREATE_COORDINATOR_TASK": ActionDefinition(
        "CREATE_COORDINATOR_TASK",
        "Escalate an unresolved pathway exception to a coordinator.",
        True,
        "create_coordinator_task",
        agent_may_self_approve=True,
    ),
}
