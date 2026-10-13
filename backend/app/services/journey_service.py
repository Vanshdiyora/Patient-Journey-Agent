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

from app.models import Journey, JourneyStep, Patient, Pathway, PathwayStep
from app.orchestration.journey_engine import JourneyEngine

ACTIVE_JOURNEY_STATUSES = ("ACTIVE", "BLOCKED")


def target_completion_hours(steps: list[PathwayStep], time_limits: dict[UUID, int]) -> int:
    """Clinical milestone days are measured from journey start, not added per step."""
    milestone_days = [step.due_after_days for step in steps if step.due_after_days is not None]
    return max(milestone_days) * 24 if milestone_days else sum(time_limits.values())


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


def find_active_patient_journey(db: Session, patient_id: UUID) -> Journey | None:
    """An ACTIVE or BLOCKED journey already running for this patient."""
    return (
        db.query(Journey)
        .filter(
            Journey.patient_id == patient_id,
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


def sync_journey_to_active_pathway(db: Session, journey_id: UUID) -> bool:
    """Move an active journey to the latest active version of its pathway."""
    journey = (
        db.query(Journey)
        .filter(Journey.id == journey_id)
        .with_for_update()
        .first()
    )
    if journey is None or journey.status not in ACTIVE_JOURNEY_STATUSES:
        return False

    source_pathway = db.query(Pathway).filter(Pathway.id == journey.pathway_id).first()
    if source_pathway is None:
        return False
    active_pathway = (
        db.query(Pathway)
        .filter(Pathway.code == source_pathway.code, Pathway.status == "ACTIVE")
        .order_by(Pathway.version.desc())
        .first()
    )
    if active_pathway is None or active_pathway.id == journey.pathway_id:
        return False

    target_steps = pathway_steps(db, active_pathway.id)
    target_by_code = {step.code: step for step in target_steps}
    journey_steps = (
        db.query(JourneyStep, PathwayStep)
        .join(PathwayStep, JourneyStep.pathway_step_id == PathwayStep.id)
        .filter(JourneyStep.journey_id == journey.id)
        .order_by(JourneyStep.id)
        .with_for_update(of=JourneyStep)
        .all()
    )
    retained_step_ids = set()
    now = datetime.now(timezone.utc)

    for journey_step, source_step in journey_steps:
        target_step = target_by_code.get(source_step.code)
        if target_step is None:
            if journey_step.status not in {"COMPLETED", "CANCELLED"}:
                journey_step.status = "CANCELLED"
                journey_step.block_reason = None
                journey_step.updated_at = now
            continue

        journey_step.pathway_step_id = target_step.id
        journey_step.owner_role = target_step.owner_role or "CLINICIAN"
        if source_step.time_limit_hours != target_step.time_limit_hours:
            journey_step.time_limit_hours = (
                target_step.time_limit_hours
                if target_step.time_limit_hours is not None
                else max(target_step.due_after_days or 1, 1) * 24
            )
            if journey_step.status in {"READY", "IN_PROGRESS", "BLOCKED"}:
                journey_step.started_at = now
                journey_step.due_at = now + timedelta(hours=journey_step.time_limit_hours)
        journey_step.updated_at = now
        retained_step_ids.add(target_step.id)

    for target_step in target_steps:
        if target_step.id in retained_step_ids:
            continue
        time_limit_hours = (
            target_step.time_limit_hours
            if target_step.time_limit_hours is not None
            else max(target_step.due_after_days or 1, 1) * 24
        )
        db.add(JourneyStep(
            id=uuid4(),
            journey_id=journey.id,
            pathway_step_id=target_step.id,
            status="PENDING",
            owner_role=target_step.owner_role or "CLINICIAN",
            time_limit_hours=time_limit_hours,
            due_at=None,
            started_at=None,
            created_at=now,
            updated_at=now,
        ))

    journey.pathway_id = active_pathway.id
    journey.pathway_version = active_pathway.version
    journey.target_completion_at = journey.started_at + timedelta(hours=target_completion_hours(
        target_steps,
        {step.id: step.time_limit_hours or max(step.due_after_days or 1, 1) * 24 for step in target_steps},
    ))
    journey.updated_at = now
    db.flush()
    JourneyEngine(db).evaluate(journey.id)
    return True


def start_journey_for_patient(
    db: Session,
    patient_id: UUID,
    pathway_id: UUID,
    priority: str,
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
    if priority not in {"CRITICAL", "HIGH", "MEDIUM", "LOW"}:
        raise HTTPException(422, "Journey priority must be CRITICAL, HIGH, MEDIUM, or LOW")
    # Serialize starts across REST and chat so a patient cannot gain two active journeys.
    db.query(Patient.id).filter(Patient.id == patient_id).with_for_update().first()
    pathway = get_active_pathway(db, pathway_id)

    existing = find_active_patient_journey(db, patient_id)
    if existing:
        raise HTTPException(409, "This patient already has an active care journey")

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
    total_hours = target_completion_hours(templates, time_limits)
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
            owner_role=template.owner_role or "CLINICIAN",
            time_limit_hours=time_limits[template.id],
            due_at=None,
            started_at=None,
            created_at=now, updated_at=now,
        ))
    db.flush()
    JourneyEngine(db).evaluate(journey.id)
    return journey
