from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy.orm import Session
from app.models import Journey, JourneyStep, PathwayStep, ExceptionRecord, PatientEvent, ActionExecution
from app.rules.journey_rule_engine import JourneyRuleEngine
from app.rules.escalation_engine import EscalationEngine

class JourneyEngine:
    def __init__(self, db: Session): self.db = db

    def evaluate(self, journey_id: UUID):
        return JourneyRuleEngine(self.db).evaluate(journey_id)

    def process_event(self, journey_id: UUID, event: PatientEvent):
        self._apply_evidence(event)
        result = self.evaluate(journey_id)
        self._create_exceptions_for_blockers(journey_id, result)
        self.db.flush()
        return self._serialize_result(result)

    # Event types that can complete a clinical step. Patient-channel sources
    # (carepath-ui-patient / patient-portal / patient) are NEVER trusted to
    # complete steps; verification must come from staff or trusted integrations.
    STEP_COMPLETING_EVENT_TYPES = {
        "STEP_COMPLETED", "FOLLOWUP_COMPLETED", "APPOINTMENT_COMPLETED",
        "LAB_RESULT_AVAILABLE", "DISCHARGE_COMPLETED",
    }
    UNTRUSTED_SOURCES = {"carepath-ui-patient", "patient-portal", "patient"}

    def _apply_evidence(self, event):
        payload = event.payload or {}
        step_code = payload.get("step_code")
        if not step_code:
            return
        # A step can only be completed by an event that is EXPLICITLY verified.
        # Missing verified must be treated as unverified (fail closed).
        if payload.get("verified") is not True:
            return
        if event.source in self.UNTRUSTED_SOURCES:
            return
        journey_steps = self.db.query(JourneyStep).filter(JourneyStep.journey_id == event.journey_id).all()
        for js in journey_steps:
            ps = self.db.query(PathwayStep).filter(PathwayStep.id == js.pathway_step_id).first()
            if ps and ps.code == step_code:
                if event.event_type in self.STEP_COMPLETING_EVENT_TYPES or payload.get("step_completed") is True:
                    js.status = "COMPLETED"
                    js.completed_at = event.event_time
                    js.block_reason = None
                    js.updated_at = datetime.now(timezone.utc)

    def _create_exceptions_for_blockers(self, journey_id, result):
        if not result: return
        for item in result["steps"]:
            if not item.get("blocked"): continue
            step_id = UUID(item["step_id"])
            existing = self.db.query(ExceptionRecord).filter(
                ExceptionRecord.journey_id == journey_id,
                ExceptionRecord.journey_step_id == step_id,
                ExceptionRecord.status.in_(["OPEN", "IN_PROGRESS"]),
            ).first()
            if existing: continue
            journey = result["journey"]
            severity = "CRITICAL" if journey.priority == "CRITICAL" else "HIGH" if journey.priority == "HIGH" else "MEDIUM"
            self.db.add(ExceptionRecord(
                id=__import__('uuid').uuid4(), journey_id=journey_id, journey_step_id=step_id,
                severity=severity, exception_type="DEPENDENCY_BLOCKED", title="Journey step is blocked",
                description=item.get("reason") or "Deterministic rules identified a blocker.",
                status="OPEN", recommended_action="Re-evaluate the dependency or route to the coordinator.",
                created_at=datetime.now(timezone.utc), resolved_at=None,
            ))

    @staticmethod
    def _serialize_result(result):
        if not result: return None
        return {"journey": {"id": str(result["journey"].id), "status": result["journey"].status}, "steps": result["steps"]}
