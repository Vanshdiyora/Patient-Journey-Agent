from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy.orm import Session
from app.models import ActionExecution
from app.action_registry.registry import ActionRegistry
from app.orchestration.idempotency import build_idempotency_key
from app.orchestration.verification import VerificationLayer
from app.integrations.mock import MockSchedulingService, MockCommunicationService, MockDocumentService

class ActionExecutor:
    def __init__(self, db: Session):
        self.db = db
        self.registry = ActionRegistry()
        self.verifier = VerificationLayer()
        self.scheduling = MockSchedulingService()
        self.communication = MockCommunicationService()
        self.document = MockDocumentService()

    def execute(self, journey_id, journey_step_id, action_type, payload, requested_by="SUPERVISOR"):
        definition = self.registry.validate(action_type)
        key = build_idempotency_key(journey_id, journey_step_id, action_type, payload)
        existing = self.db.query(ActionExecution).filter(ActionExecution.idempotency_key == key).first()
        if existing:
            return existing, {"duplicate": True, "verified": existing.status == "SUCCESS"}
        execution = ActionExecution(
            id=uuid4(), journey_id=journey_id, journey_step_id=journey_step_id,
            action_type=action_type, requested_by=requested_by, status="EXECUTING",
            idempotency_key=key, request_payload=payload or {}, response_payload=None,
            requested_at=datetime.now(timezone.utc), completed_at=None,
        )
        self.db.add(execution); self.db.flush()
        try:
            if action_type == "REQUEST_DOCUMENT": response = self.document.request_document(payload)
            elif action_type == "SEND_REMINDER": response = self.communication.send_reminder(payload)
            elif action_type == "REQUEST_APPOINTMENT": response = self.scheduling.request_appointment(payload)
            elif action_type == "RESCHEDULE_APPOINTMENT": response = self.scheduling.reschedule_appointment(payload)
            elif action_type == "CREATE_COORDINATOR_TASK": response = {"accepted": True, "status": "TASK_CREATED", "external_reference": f"MOCK-TASK-{uuid4().hex[:10]}", "payload": payload}
            else: raise ValueError(f"No executor for {action_type}")
            verification = self.verifier.verify(action_type, response)
            execution.status = "SUCCESS"
            execution.response_payload = {**response, "verification": verification}
            execution.completed_at = datetime.now(timezone.utc)
        except Exception as exc:
            execution.status = "FAILED"
            execution.error_message = str(exc)
            execution.response_payload = {"accepted": False, "reason": str(exc)}
            execution.completed_at = datetime.now(timezone.utc)
        self.db.flush()
        return execution, {"duplicate": False, "verified": execution.status == "SUCCESS"}
