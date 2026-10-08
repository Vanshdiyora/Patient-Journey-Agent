from uuid import UUID
from sqlalchemy.orm import Session
from app.models import Dependency, JourneyStep, PatientEvent

class DependencyEngine:
    """Deterministic dependency evaluation. No LLM calls."""
    def __init__(self, db: Session): self.db = db

    def evaluate_for_step(self, journey_id: UUID, target_step_id: UUID):
        deps = self.db.query(Dependency).filter(Dependency.target_step_id == target_step_id).all()
        results = []
        for dep in deps:
            source = self.db.query(JourneyStep).filter(JourneyStep.pathway_step_id == dep.source_step_id, JourneyStep.journey_id == journey_id).first()
            if not source:
                results.append({"dependency_id": str(dep.id), "satisfied": False, "blocking": dep.blocking, "reason": "Source step is not present in journey"})
                continue
            satisfied = False
            evidence = []
            if dep.condition_type == "COMPLETED":
                satisfied = source.status == "COMPLETED"
                reason = "Source step completed" if satisfied else "Source step is not completed"
            elif dep.condition_type == "RESULT_AVAILABLE":
                target = self.db.query(JourneyStep).filter(
                    JourneyStep.pathway_step_id == dep.target_step_id,
                    JourneyStep.journey_id == journey_id,
                ).first()
                events = (
                    self.db.query(PatientEvent)
                    .filter(PatientEvent.journey_id == journey_id)
                    .order_by(PatientEvent.event_time.desc())
                    .limit(50)
                    .all()
                )
                for event in events:
                    payload = event.payload or {}
                    evidence_step_id = payload.get("journey_step_id")
                    targets_this_step = (
                        target is not None
                        and evidence_step_id is not None
                        and str(evidence_step_id) == str(target.id)
                    )
                    if targets_this_step and (
                        event.event_type == "LAB_RESULT_AVAILABLE"
                        or payload.get("result_available") is True
                    ):
                        evidence.append({"event_id": str(event.id), "event_type": event.event_type})
                        satisfied = True
                        break
                reason = "Required result evidence found" if satisfied else "Required result evidence is missing"
            elif dep.condition_type == "APPROVED":
                target = self.db.query(JourneyStep).filter(
                    JourneyStep.pathway_step_id == dep.target_step_id,
                    JourneyStep.journey_id == journey_id,
                ).first()
                events = self.db.query(PatientEvent).filter(PatientEvent.journey_id == journey_id).order_by(PatientEvent.event_time.desc()).limit(50).all()
                for event in events:
                    payload = event.payload or {}
                    approval_for_this_step = (
                        event.event_type == "STEP_APPROVAL_EVIDENCE_RECORDED"
                        and target is not None
                        and str(payload.get("journey_step_id")) == str(target.id)
                        and payload.get("approved") is True
                    )
                    if approval_for_this_step or event.event_type in {"AUTHORIZATION_APPROVED", "APPROVAL_RECEIVED"}:
                        evidence.append({"event_id": str(event.id), "event_type": event.event_type})
                        satisfied = True
                        break
                reason = "Approval evidence found" if satisfied else "Required approval evidence is missing"
            else:
                satisfied = source.status == "COMPLETED"
                reason = "Source step completed" if satisfied else "Source step is not completed"
            results.append({"dependency_id": str(dep.id), "satisfied": satisfied, "blocking": dep.blocking, "reason": reason, "condition_type": dep.condition_type, "source_step_id": str(dep.source_step_id), "target_step_id": str(dep.target_step_id), "evidence": evidence})
        return results

    def is_blocked(self, results):
        blockers = [r for r in results if r.get("blocking") and not r.get("satisfied")]
        return bool(blockers), blockers
