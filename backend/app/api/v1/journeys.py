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
from app.models import Journey, JourneyStep, PatientEvent, Patient, PathwayStep
from app.schemas import JourneyResponse, JourneyStepResponse
from app.orchestration.journey_engine import JourneyEngine
from app.orchestration.langgraph_supervisor import SupervisorGraph
from app.agents.supervisor.tools import build_supervisor_context

router = APIRouter()


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
    if status:
        q = q.filter(Journey.status == status)
    if priority:
        q = q.filter(Journey.priority == priority)
    total = q.with_entities(func.count()).scalar() or 0
    return {
        "items": q.order_by(Journey.updated_at.desc()).offset(offset).limit(limit).all(),
        "total": total,
        "limit": limit,
        "offset": offset,
        "scope": scope_note(user),
    }


@router.get("/journeys/{journey_id}", response_model=JourneyResponse)
def get_journey(journey_id: UUID, db: Session = Depends(get_db), user=Depends(require_staff)):
    return get_journey_scoped(journey_id, db, user)


@router.get("/journeys/{journey_id}/steps", response_model=list[JourneyStepResponse])
def steps(journey_id: UUID, db: Session = Depends(get_db), user=Depends(require_staff)):
    get_journey_scoped(journey_id, db, user)
    return (
        db.query(JourneyStep)
        .filter(JourneyStep.journey_id == journey_id)
        .order_by(JourneyStep.due_at)
        .all()
    )


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
