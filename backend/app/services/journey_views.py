"""Journey read models shared by staff and patient endpoints."""
from datetime import timedelta
from sqlalchemy.orm import Session

from app.models import Journey, JourneyStep, Pathway, PathwayStep, PatientEvent
from app.schemas.journey import JourneyResponse, JourneyStepResponse


def journey_with_pathway(journey: Journey, pathway_name: str | None) -> dict:
    return {**JourneyResponse.model_validate(journey).model_dump(), "pathway_name": pathway_name}


def journeys_with_pathways(db: Session, journeys: list[Journey]) -> list[dict]:
    ids = {journey.pathway_id for journey in journeys}
    names = {pathway.id: pathway.name for pathway in db.query(Pathway).filter(Pathway.id.in_(ids)).all()} if ids else {}
    return [journey_with_pathway(journey, names.get(journey.pathway_id)) for journey in journeys]


def steps_with_pathway_details(db: Session, journey_id) -> list[dict]:
    journey = db.query(Journey).filter(Journey.id == journey_id).first()
    if journey is None:
        return []
    rows = (
        db.query(JourneyStep, PathwayStep)
        .join(PathwayStep, JourneyStep.pathway_step_id == PathwayStep.id)
        .filter(
            JourneyStep.journey_id == journey_id,
            PathwayStep.pathway_id == journey.pathway_id,
        )
        .order_by(PathwayStep.sequence_number)
        .all()
    )
    step_ids = {step.id for step, _template in rows}
    pending_step_ids = {
        event.payload.get("journey_step_id")
        for event in db.query(PatientEvent)
        .filter(
            PatientEvent.journey_id == journey_id,
            PatientEvent.event_type == "PATIENT_STEP_SUBMITTED",
            PatientEvent.processed.is_(False),
        )
        .all()
        if (event.payload or {}).get("journey_step_id") in {str(step_id) for step_id in step_ids}
    }
    return [
        {
            **JourneyStepResponse.model_validate(step).model_dump(),
            "name": template.name,
            "description": template.description,
            "sequence_number": template.sequence_number,
            "owner_role": step.owner_role or template.owner_role or "CLINICIAN",
            "time_limit_hours": step.time_limit_hours,
            "due_after_days": template.due_after_days,
            "planned_due_at": journey.started_at + timedelta(days=template.due_after_days) if template.due_after_days is not None else None,
            "patient_submission_pending": str(step.id) in pending_step_ids,
        }
        for step, template in rows
    ]
