from uuid import UUID
from sqlalchemy.orm import Session
from app.models import Journey, Pathway, PathwayStep, PatientEvent, JourneyStep

def build_context(db: Session, journey_id: UUID, event_limit: int = 12):
    journey = db.query(Journey).filter(Journey.id == journey_id).first()
    if not journey: return None
    pathway = db.query(Pathway).filter(Pathway.id == journey.pathway_id).first()
    steps = db.query(PathwayStep).filter(PathwayStep.pathway_id == journey.pathway_id).order_by(PathwayStep.sequence_number).all()
    events = db.query(PatientEvent).filter(PatientEvent.journey_id == journey_id).order_by(PatientEvent.event_time.desc()).limit(event_limit).all()
    journey_steps = {str(s.pathway_step_id): s for s in db.query(JourneyStep).filter(JourneyStep.journey_id == journey_id).all()}
    return {
        "journey": {"id": str(journey.id), "patient_id": str(journey.patient_id), "pathway_id": str(journey.pathway_id), "status": journey.status, "priority": journey.priority},
        "pathway": {"code": pathway.code if pathway else None, "name": pathway.name if pathway else None, "description": pathway.description if pathway else None},
        "steps": [
            {"id": str(s.id), "code": s.code, "name": s.name, "type": s.step_type, "required": s.required, "sequence": s.sequence_number, "status": journey_steps.get(str(s.id)).status if journey_steps.get(str(s.id)) else None, "completion_criteria": s.completion_criteria}
            for s in steps
        ],
        "recent_events": [
            {"id": str(e.id), "type": e.event_type, "source": e.source, "event_time": e.event_time.isoformat(), "payload": e.payload}
            for e in events
        ],
    }
