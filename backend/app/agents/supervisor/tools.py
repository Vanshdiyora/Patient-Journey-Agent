from uuid import UUID
from sqlalchemy.orm import Session
from app.models import Journey, JourneyStep, PathwayStep
from app.rules.journey_rule_engine import JourneyRuleEngine
from app.action_registry.registry import ActionRegistry


def evaluate_deterministically(db: Session, journey_id: UUID):
    result = JourneyRuleEngine(db).evaluate(journey_id)
    if not result: return None
    ready = [x for x in result["steps"] if x.get("ready")]
    blocked = [x for x in result["steps"] if x.get("blocked")]
    return {"journey": result["journey"], "steps": result["steps"], "ready_steps": ready, "blocked_steps": blocked}


def build_supervisor_context(db: Session, journey_id: UUID):
    result = evaluate_deterministically(db, journey_id)
    if not result: return None
    journey = result["journey"]
    rows = []
    for item in result["steps"]:
        step = db.query(JourneyStep).filter(JourneyStep.id == UUID(item["step_id"])).first()
        pathway_step = db.query(PathwayStep).filter(PathwayStep.id == step.pathway_step_id).first() if step else None
        rows.append({
            "journey_step_id": item["step_id"],
            "step_code": pathway_step.code if pathway_step else None,
            "step_name": pathway_step.name if pathway_step else None,
            "step_type": pathway_step.step_type if pathway_step else None,
            "status": item["status"],
            "blocked": item["blocked"],
            "ready": item["ready"],
            "reason": item.get("reason"),
        })
    return {"journey": {"id": str(journey.id), "status": journey.status, "priority": journey.priority}, "steps": rows, "allowed_action_types": list(ActionRegistry().get(a).action_type for a in ["REQUEST_DOCUMENT","SEND_REMINDER","REQUEST_APPOINTMENT","RESCHEDULE_APPOINTMENT","CREATE_COORDINATOR_TASK"])}
