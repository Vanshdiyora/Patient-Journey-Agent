from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy.orm import Session
from app.models import Journey, JourneyStep
from app.rules.dependency_engine import DependencyEngine
from app.rules.deadline_engine import DeadlineEngine

class JourneyRuleEngine:
    def __init__(self, db: Session):
        self.db = db
        self.dependencies = DependencyEngine(db)
        self.deadlines = DeadlineEngine()

    def evaluate(self, journey_id: UUID):
        journey = self.db.query(Journey).filter(Journey.id == journey_id).first()
        if not journey:
            return None
        now = datetime.now(timezone.utc)
        steps = self.db.query(JourneyStep).filter(JourneyStep.journey_id == journey_id).order_by(JourneyStep.due_at.asc()).all()
        evaluations = []
        for step in steps:
            if step.status in {"COMPLETED", "CANCELLED"}:
                evaluations.append({"step_id": str(step.id), "status": step.status, "ready": False, "blocked": False, "reason": None})
                continue
            step.last_evaluated_at = now
            dep_results = self.dependencies.evaluate_for_step(journey_id, step.pathway_step_id)
            blocked, blockers = self.dependencies.is_blocked(dep_results)
            deadline = self.deadlines.evaluate(step, now)
            if blocked:
                step.status = "BLOCKED"
                step.block_reason = "; ".join(b["reason"] for b in blockers)
            elif deadline["overdue"] and step.status in {"PENDING", "READY"}:
                step.status = "BLOCKED"
                step.block_reason = deadline["reason"]
            elif step.status == "PENDING":
                prior_active = any(s.status not in {"COMPLETED", "CANCELLED"} and s.due_at and s.due_at < step.due_at for s in steps if s.id != step.id)
                if not prior_active:
                    step.status = "READY"
                    step.block_reason = None
            evaluations.append({"step_id": str(step.id), "status": step.status, "ready": step.status == "READY", "blocked": step.status == "BLOCKED", "reason": step.block_reason, "dependency_results": dep_results})
        if steps and all(s.status in {"COMPLETED", "CANCELLED"} for s in steps):
            journey.status = "COMPLETED"
            journey.completed_at = journey.completed_at or now
        elif any(s.status == "BLOCKED" for s in steps):
            journey.status = "BLOCKED"
        else:
            journey.status = "ACTIVE"
        journey.updated_at = now
        self.db.flush()
        return {"journey": journey, "steps": evaluations}
