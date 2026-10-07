from datetime import datetime, timedelta, timezone
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.authorization import (
    STAFF_ROLES,
    get_journey_for_action,
    get_journey_scoped,
    require_staff,
    scope_patient_ids,
    scope_note,
)
from app.models import Journey, Patient, Pathway, PathwayStep
from app.schemas import JourneyResponse, JourneyStepResponse
from app.schemas.journey import JourneyStepTimeLimitUpdate
from app.orchestration.journey_engine import JourneyEngine
from app.orchestration.langgraph_supervisor import SupervisorGraph
from app.agents.supervisor.tools import build_supervisor_context
from app.api.v1.journey_views import journeys_with_pathways, steps_with_pathway_details

router = APIRouter()

VALID_STATUSES = ("ACTIVE", "BLOCKED", "COMPLETED", "CANCELLED")
VALID_PRIORITIES = ("CRITICAL", "HIGH", "MEDIUM", "LOW")


def _normalize_filter(raw: str | None, valid: tuple[str, ...]) -> list[str]:
    """
    Accept comma-separated values in any case (UI sends lowercase; the DB enum
    is uppercase, e.g. "active,blocked" -> ["ACTIVE", "BLOCKED"]).
    """
    if not raw:
        return []
    values = []
    for part in raw.split(","):
        part = part.strip().upper()
        if not part:
            continue
        if part not in valid:
            raise HTTPException(422, f"Unknown value: {part}")
        values.append(part)
    return values


def _with_patient_names(db: Session, journeys: list[Journey]) -> list[dict]:
    """Serialize journeys with patient identity so panels can show real names."""
    patient_ids = {j.patient_id for j in journeys}
    patients = (
        db.query(Patient)
        .filter(Patient.id.in_(patient_ids))
        .all()
        if patient_ids
        else []
    )
    by_id = {p.id: p for p in patients}
    pathways = (
        db.query(Pathway)
        .filter(Pathway.id.in_({j.pathway_id for j in journeys}))
        .all()
        if patient_ids
        else []
    )
    pathway_names = {w.id: w.name for w in pathways}
    rows = []
    for j in journeys:
        p = by_id.get(j.patient_id)
        rows.append(
            {
                "id": j.id,
                "patient_id": j.patient_id,
                "pathway_id": j.pathway_id,
                "pathway_version": j.pathway_version,
                "status": j.status,
                "priority": j.priority,
                "started_at": j.started_at,
                "target_completion_at": j.target_completion_at,
                "completed_at": j.completed_at,
                "created_at": j.created_at,
                "updated_at": j.updated_at,
                "patient_name": f"{p.first_name} {p.last_name}" if p else None,
                "patient_reference": p.patient_reference if p else None,
                "pathway_name": pathway_names.get(j.pathway_id),
            }
        )
    return rows


@router.get("/journeys")
def list_journeys(
    status: str | None = None,
    priority: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user=Depends(require_staff),
):
    q = db.query(Journey)
    patient_ids = scope_patient_ids(db, user)
    if patient_ids is not None:
        q = q.filter(Journey.patient_id.in_(patient_ids))
    statuses = _normalize_filter(status, VALID_STATUSES)
    if statuses:
        q = q.filter(Journey.status.in_(statuses))
    priorities = _normalize_filter(priority, VALID_PRIORITIES)
    if priorities:
        q = q.filter(Journey.priority.in_(priorities))
    total = q.with_entities(func.count()).scalar() or 0
    items = q.order_by(Journey.updated_at.desc()).offset(offset).limit(limit).all()
    return {
        "items": _with_patient_names(db, items),
        "total": total,
        "limit": limit,
        "offset": offset,
        "scope": scope_note(user),
    }


@router.get("/journeys/available-pathways")
def available_pathways(db: Session = Depends(get_db), user=Depends(require_staff)):
    pathways = db.query(Pathway).filter(Pathway.status == "ACTIVE").order_by(Pathway.name).all()
    return [
        {"id": pathway.id, "code": pathway.code, "name": pathway.name,
         "description": pathway.description, "version": pathway.version,
         "steps": [
             {
                 "id": step.id,
                 "code": step.code,
                 "name": step.name,
                 "description": step.description,
                 "step_type": step.step_type,
                 "required": step.required,
                 "sequence_number": step.sequence_number,
                 "time_limit_hours": step.time_limit_hours,
             }
             for step in db.query(PathwayStep)
             .filter(PathwayStep.pathway_id == pathway.id)
             .order_by(PathwayStep.sequence_number)
             .all()
         ]}
        for pathway in pathways
    ]


@router.get("/journeys/{journey_id}", response_model=JourneyResponse)
def get_journey(journey_id: UUID, db: Session = Depends(get_db), user=Depends(require_staff)):
    journey = get_journey_scoped(journey_id, db, user)
    return journeys_with_pathways(db, [journey])[0]


@router.get("/journeys/{journey_id}/steps", response_model=list[JourneyStepResponse])
def steps(journey_id: UUID, db: Session = Depends(get_db), user=Depends(require_staff)):
    get_journey_scoped(journey_id, db, user)
    return steps_with_pathway_details(db, journey_id)


@router.patch("/journeys/{journey_id}/steps/{step_id}/time-limit")
def update_step_time_limit(
    journey_id: UUID,
    step_id: UUID,
    data: JourneyStepTimeLimitUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_staff),
):
    get_journey_scoped(journey_id, db, user)
    step = (
        db.query(JourneyStep)
        .filter(JourneyStep.id == step_id, JourneyStep.journey_id == journey_id)
        .first()
    )
    if not step:
        raise HTTPException(404, "Journey step not found")
    if step.status in {"COMPLETED", "CANCELLED"}:
        raise HTTPException(409, "Time limits cannot be changed for completed or cancelled steps")

    now = datetime.now(timezone.utc)
    step.time_limit_hours = data.time_limit_hours
    if step.status in {"READY", "IN_PROGRESS"}:
        step.started_at = now
        step.due_at = now + timedelta(hours=data.time_limit_hours)
    elif step.status == "BLOCKED" and step.due_at is not None:
        step.status = "READY"
        step.started_at = now
        step.due_at = now + timedelta(hours=data.time_limit_hours)
        step.block_reason = None
    step.updated_at = now
    JourneyEngine(db).evaluate(journey_id)
    db.commit()
    db.refresh(step)
    return steps_with_pathway_details(db, journey_id)


@router.post("/journeys/{journey_id}/evaluate")
def evaluate(journey_id: UUID, db: Session = Depends(get_db), user=Depends(get_current_user)):
    journey = get_journey_for_action(journey_id, db, user, allowed_roles=STAFF_ROLES)
    result = JourneyEngine(db).evaluate(journey.id)
    if not result:
        raise HTTPException(404, "Journey not found")
    db.commit()
    db.refresh(result["journey"])
    return {"journey": result["journey"], "steps": result["steps"]}


@router.get("/journeys/{journey_id}/orchestration-context")
def orchestration_context(journey_id: UUID, db: Session = Depends(get_db), user=Depends(require_staff)):
    get_journey_scoped(journey_id, db, user)
    context = build_supervisor_context(db, journey_id)
    if not context:
        raise HTTPException(404, "Journey not found")
    db.commit()
    return context


@router.post("/journeys/{journey_id}/orchestrate")
def orchestrate(journey_id: UUID, db: Session = Depends(get_db), user=Depends(get_current_user)):
    # Patients can never orchestrate; staff must be in scope for this journey.
    journey = get_journey_for_action(journey_id, db, user, allowed_roles=STAFF_ROLES)
    try:
        result = SupervisorGraph(db).run(journey.id)
        return {
            "journey_id": journey.id,
            "status": result.get("status"),
            "decision": result.get("decision"),
            "result": result.get("result"),
            "calls": result.get("calls", []),
        }
    except Exception as exc:
        db.rollback()
        raise HTTPException(502, f"Orchestration failed: {exc}")
