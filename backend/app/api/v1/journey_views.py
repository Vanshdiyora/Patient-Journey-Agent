"""Journey read models shared by staff and patient endpoints."""
from sqlalchemy.orm import Session

from app.models import Journey, JourneyStep, Pathway, PathwayStep
from app.schemas.journey import JourneyResponse, JourneyStepResponse


def journey_with_pathway(journey: Journey, pathway_name: str | None) -> dict:
    return {**JourneyResponse.model_validate(journey).model_dump(), "pathway_name": pathway_name}


def journeys_with_pathways(db: Session, journeys: list[Journey]) -> list[dict]:
    ids = {journey.pathway_id for journey in journeys}
    names = {pathway.id: pathway.name for pathway in db.query(Pathway).filter(Pathway.id.in_(ids)).all()} if ids else {}
    return [journey_with_pathway(journey, names.get(journey.pathway_id)) for journey in journeys]


def steps_with_pathway_details(db: Session, journey_id) -> list[dict]:
    rows = (
        db.query(JourneyStep, PathwayStep)
        .join(PathwayStep, JourneyStep.pathway_step_id == PathwayStep.id)
        .filter(JourneyStep.journey_id == journey_id)
        .order_by(PathwayStep.sequence_number)
        .all()
    )
    return [
        {
            **JourneyStepResponse.model_validate(step).model_dump(),
            "name": template.name,
            "description": template.description,
            "sequence_number": template.sequence_number,
            "time_limit_hours": step.time_limit_hours,
        }
        for step, template in rows
    ]
