from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.action_registry.registry import ActionRegistry
from app.core.config import settings
from app.core.exceptions import ActionNotAllowedError
from app.integrations.email_delivery import EmailPatientService
from app.integrations.mock import MockCommunicationService, MockDocumentService, MockSchedulingService
from app.models import ActionExecution, ExceptionRecord, Journey
from app.orchestration.idempotency import build_idempotency_key
from app.orchestration.verification import VerificationLayer


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ActionExecutor:
    """
    Runs registry actions. Patient-facing actions (reminder, document request,
    appointment request/reschedule) are delivered by email when SMTP is
    configured and simulated otherwise; the response says which ("delivery").
    Coordinator tasks are real in-app tasks (an exception visible to staff).
    Approval-gated actions are only recorded here and run when staff approve.
    """

    def __init__(self, db: Session):
        self.db = db
        self.registry = ActionRegistry()
        self.verifier = VerificationLayer()
        if settings.email_enabled:
            email = EmailPatientService(db)
            self.scheduling = self.communication = self.document = email
            self.delivery = "email"
        else:
            self.scheduling = MockSchedulingService()
            self.communication = MockCommunicationService()
            self.document = MockDocumentService()
            self.delivery = "mock"

    # ------------------------------------------------------------------ run
    def execute(self, journey_id, journey_step_id, action_type, payload, requested_by="SUPERVISOR"):
        definition = self.registry.validate(action_type)
        key = build_idempotency_key(journey_id, journey_step_id, action_type, payload)
        existing = self.db.query(ActionExecution).filter(ActionExecution.idempotency_key == key).first()
        if existing:
            return existing, {
                "duplicate": True,
                "verified": existing.status == "SUCCESS",
                "awaiting_approval": existing.status == "REQUESTED",
                "delivery": (existing.response_payload or {}).get("delivery"),
            }
        execution = ActionExecution(
            id=uuid4(), journey_id=journey_id, journey_step_id=journey_step_id,
            action_type=action_type, requested_by=requested_by, status="EXECUTING",
            idempotency_key=key, request_payload=payload or {}, response_payload=None,
            requested_at=_now(), completed_at=None,
        )
        if definition.requires_approval:
            # Never run by an agent: recorded so staff can approve or reject it.
            execution.status = "REQUESTED"
            execution.response_payload = {
                "accepted": False, "status": "AWAITING_APPROVAL",
                "reason": "This action needs staff approval before it can run.",
            }
            self.db.add(execution)
            self.db.flush()
            return execution, {"duplicate": False, "verified": False, "awaiting_approval": True, "delivery": None}
        self.db.add(execution)
        self.db.flush()
        self._run(execution, action_type, payload or {})
        self.db.flush()
        return execution, {
            "duplicate": False, "verified": execution.status == "SUCCESS", "awaiting_approval": False,
            "delivery": (execution.response_payload or {}).get("delivery"),
        }

    def _run(self, execution: ActionExecution, action_type: str, payload: dict, extra: dict | None = None):
        try:
            if action_type == "REQUEST_DOCUMENT":
                response = self.document.request_document(payload)
            elif action_type == "SEND_REMINDER":
                response = self.communication.send_reminder(payload)
            elif action_type == "REQUEST_APPOINTMENT":
                response = self.scheduling.request_appointment(payload)
            elif action_type == "RESCHEDULE_APPOINTMENT":
                response = self.scheduling.reschedule_appointment(payload)
            elif action_type == "CREATE_COORDINATOR_TASK":
                response = self._create_coordinator_task(execution, payload)
            else:
                raise ActionNotAllowedError(f"No executor for {action_type}")
            response.setdefault("delivery", self.delivery)
            verification = self.verifier.verify(action_type, response)
            execution.status = "SUCCESS"
            execution.response_payload = {**response, **(extra or {}), "verification": verification}
        except Exception as exc:  # noqa: BLE001 - recorded on the execution, never raised
            execution.status = "FAILED"
            execution.error_message = str(exc)[:500]
            execution.response_payload = {"accepted": False, "reason": str(exc)[:500], **(extra or {})}
        execution.completed_at = _now()

    def _create_coordinator_task(self, execution: ActionExecution, payload: dict) -> dict:
        """A real, in-app task: an open item on the Exceptions page for coordinators."""
        journey = self.db.query(Journey).filter(Journey.id == execution.journey_id).first()
        severity = journey.priority if journey and journey.priority in ("CRITICAL", "HIGH") else "MEDIUM"
        step = payload.get("step_name") or "a journey step"
        task = ExceptionRecord(
            id=uuid4(), journey_id=execution.journey_id, journey_step_id=execution.journey_step_id,
            severity=severity, exception_type="COORDINATOR_TASK", title=f"Coordinator task: {step}",
            description=payload.get("reason") or f"A coordinator needs to follow up on {step}.",
            status="OPEN", recommended_action="Contact the patient or the responsible team and resolve the blocker.",
            created_at=_now(), resolved_at=None,
        )
        self.db.add(task)
        self.db.flush()
        return {
            "accepted": True, "status": "TASK_CREATED", "delivery": "in_app",
            "external_reference": f"TASK-{str(task.id)[:8].upper()}", "task_id": str(task.id),
        }

    # ------------------------------------------------------------- approvals
    def _close_approval_exception(self, execution: ActionExecution, note: str):
        item = self.db.query(ExceptionRecord).filter(
            ExceptionRecord.journey_id == execution.journey_id,
            ExceptionRecord.journey_step_id == execution.journey_step_id,
            ExceptionRecord.exception_type == "ACTION_AWAITING_APPROVAL",
            ExceptionRecord.status.in_(("OPEN", "IN_PROGRESS")),
        ).first()
        if item:
            item.status = "RESOLVED"
            item.resolved_at = _now()
            item.recommended_action = note

    def approve(self, execution: ActionExecution, user) -> ActionExecution:
        """Run an action that was waiting for approval, on behalf of `user`."""
        if execution.status != "REQUESTED":
            raise ValueError(f"Only actions awaiting approval can be approved (this one is {execution.status.lower()}).")
        execution.status = "EXECUTING"
        decision = {"decision": "APPROVED", "by_user_id": str(user.id), "by_role": user.role, "at": _now().isoformat()}
        self._run(execution, execution.action_type, execution.request_payload or {}, extra={"approval": decision})
        self._close_approval_exception(execution, f"Approved by {user.display_name} and carried out.")
        self.db.flush()
        return execution

    def reject(self, execution: ActionExecution, user, note: str | None = None) -> ActionExecution:
        if execution.status != "REQUESTED":
            raise ValueError(f"Only actions awaiting approval can be rejected (this one is {execution.status.lower()}).")
        execution.status = "CANCELLED"
        execution.completed_at = _now()
        execution.response_payload = {
            "accepted": False, "status": "REJECTED", "reason": note or "Rejected by staff.",
            "approval": {"decision": "REJECTED", "by_user_id": str(user.id), "by_role": user.role, "at": _now().isoformat()},
        }
        self._close_approval_exception(execution, f"Rejected by {user.display_name}.")
        self.db.flush()
        return execution
