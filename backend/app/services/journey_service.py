"""
Journey lifecycle business logic.

Shared by the REST API (POST /patients/{id}/journeys) and the chatbot tool
registry so both paths enforce identical rules: active pathway required, no
duplicate active journey per pathway, step snapshot with time limits, and a
deterministic evaluation after creation. The chatbot never re-implements this;
it calls the same functions the API calls.
"""
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Journey, JourneyStep, Pathway, PathwayStep
from app.orchestration.journey_engine import JourneyEngine

ACTIVE_JOURNEY_STATUSES = ("ACTIVE", "BLOCKED")


def get_active_pathway(db: Session, pathway_id: UUID) -> Pathway:
    """Return the pathway if it exists and is ACTIVE, else 422."""
    pathway = (
        db.query(Pathway)
        .filter(Pathway.id == pathway_id, Pathway.status == "ACTIVE")
        .first()
    )
    if not pathway:
        raise HTTPException(422, "Select an active care pathway")
    return pathway


def find_active_journey(db: Session, patient_id: UUID, pathway_id: UUID) -> Journey | None:
    """Existing ACTIVE/BLOCKED journey for this patient + pathway code, across versions."""
    pathway = db.query(Pathway).filter(Pathway.id == pathway_id).first()
    if pathway is None:
        return None
    return (
        db.query(Journey)
        .join(Pathway, Journey.pathway_id == Pathway.id)
        .filter(
            Journey.patient_id == patient_id,
            Pathway.code == pathway.code,
            Journey.status.in_(ACTIVE_JOURNEY_STATUSES),
        )
        .first()
    )


def pathway_steps(db: Session, pathway_id: UUID) -> list[PathwayStep]:
    return (
        db.query(PathwayStep)
        .filter(PathwayStep.pathway_id == pathway_id)
        .order_by(PathwayStep.sequence_number)
        .all()
    )


def start_journey_for_patient(
    db: Session,
    patient_id: UUID,
    pathway_id: UUID,
    priority: str = "MEDIUM",
    step_time_limits: dict[UUID, int] | None = None,
) -> Journey:
    """
    Create a journey and its pathway-step snapshot for a patient.

    Raises HTTPException(422/409) on business-rule violations. The caller owns
    patient-existence/scope checks and the final commit; this function flushes
    and evaluates but does not commit, so a caller can run it inside a larger
    transaction.
    """
    overrides = step_time_limits or {}
    pathway = get_active_pathway(db, pathway_id)

    existing = find_active_journey(db, patient_id, pathway.id)
    if existing:
        raise HTTPException(409, "This patient already has an active journey for this pathway")

    templates = pathway_steps(db, pathway.id)
    if not templates:
        raise HTTPException(422, "This pathway has no care steps")

    template_ids = {step.id for step in templates}
    if not set(overrides).issubset(template_ids):
        raise HTTPException(422, "Time-limit overrides must reference steps in the selected pathway")

    time_limits = {
        step.id: overrides.get(
            step.id,
            step.time_limit_hours
            if step.time_limit_hours is not None
            else max(step.due_after_days or 1, 1) * 24,
        )
        for step in templates
    }
    total_hours = sum(time_limits.values())
    now = datetime.now(timezone.utc)
    journey = Journey(
        id=uuid4(), patient_id=patient_id, pathway_id=pathway.id,
        pathway_version=pathway.version, status="ACTIVE", priority=priority,
        started_at=now,
        target_completion_at=now + timedelta(hours=total_hours) if time_limits else None,
        created_at=now, updated_at=now,
    )
    db.add(journey)
    for template in templates:
        db.add(JourneyStep(
            id=uuid4(), journey_id=journey.id, pathway_step_id=template.id,
            status="PENDING",
            owner_role=template.owner_role or "STAFF",
            time_limit_hours=time_limits[template.id],
            due_at=None,
            started_at=None,
            created_at=now, updated_at=now,
        ))
    db.flush()
    JourneyEngine(db).evaluate(journey.id)
    return journey
