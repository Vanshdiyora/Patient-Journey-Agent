from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.authorization import (
    STAFF_ROLES,
    can_read_journey,
    get_journey_for_action,
    get_journey_scoped,
    require_staff,
    scope_patient_ids,
    scope_note,
)
from app.models import Journey, JourneyStep, Patient, PatientEvent, Pathway, PathwayStep
from app.schemas import JourneyResponse, JourneyStepResponse, OrchestrationResponse
from app.schemas.journey import JourneyStepComplete, JourneyStepTimeLimitUpdate
from app.orchestration.journey_engine import JourneyEngine
from app.orchestration.event_processor import EventProcessor
from app.orchestration.langgraph_supervisor import OrchestrationFailure, SupervisorGraph
from app.agents.supervisor.tools import build_supervisor_context
from app.services.journey_views import journeys_with_pathways, steps_with_pathway_details
from app.rules.journey_rule_engine import JourneyRuleEngine
from app.services.journey_service import sync_journey_to_active_pathway
from app.services.step_evidence_storage import (
    EvidenceFileError,
    evidence_file_path,
    save_evidence_file,
)

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
    limit: int = Query(10, ge=1, le=10),
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
    items = q.order_by(Journey.updated_at.desc(), Journey.id.desc()).offset(offset).limit(limit).all()
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
                 "owner_role": step.owner_role,
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


def _check_step_completion_permission(db, journey, step, pathway_step, user):
    owner_role = str(step.owner_role or pathway_step.owner_role or "STAFF").upper()
    if owner_role == "PATIENT":
        pending_submission = (
            db.query(PatientEvent)
            .filter(
                PatientEvent.journey_id == journey.id,
                PatientEvent.event_type == "PATIENT_STEP_SUBMITTED",
                PatientEvent.processed.is_(False),
                PatientEvent.payload["journey_step_id"].astext == str(step.id),
            )
            .first()
        )
        if not pending_submission:
            raise HTTPException(409, "The patient must submit this task before staff can review and complete it.")
        return owner_role

    allowed_roles = {
        "CLINICIAN": {"CLINICIAN"},
        "CARE_COORDINATOR": {"CARE_COORDINATOR"},
        "ADMIN": {"ADMIN"},
        "STAFF": STAFF_ROLES,
    }
    if owner_role == "AGENT":
        raise HTTPException(409, "Agent-owned steps are completed only after a verified agent action.")
    if str(user.role).upper() not in allowed_roles.get(owner_role, set()):
        raise HTTPException(403, f"This step is assigned to {owner_role.lower().replace('_', ' ')} staff.")
    return owner_role


@router.get("/journeys/{journey_id}", response_model=JourneyResponse)
def get_journey(journey_id: UUID, db: Session = Depends(get_db), user=Depends(require_staff)):
    journey = get_journey_scoped(journey_id, db, user)
    return journeys_with_pathways(db, [journey])[0]


@router.get("/journeys/{journey_id}/steps", response_model=list[JourneyStepResponse])
def steps(journey_id: UUID, db: Session = Depends(get_db), user=Depends(require_staff)):
    get_journey_scoped(journey_id, db, user)
    if sync_journey_to_active_pathway(db, journey_id):
        db.commit()
    return steps_with_pathway_details(db, journey_id)


@router.post("/journeys/{journey_id}/steps/{step_id}/complete")
def complete_journey_step(
    journey_id: UUID,
    step_id: UUID,
    data: JourneyStepComplete,
    db: Session = Depends(get_db),
    user=Depends(require_staff),
):
    # Serialize step completion per journey before locking an individual step.
    # The evaluator updates multiple steps, so taking step locks first lets
    # concurrent completions deadlock while each waits for the other's step.
    journey = (
        db.query(Journey)
        .filter(Journey.id == journey_id)
        .with_for_update()
        .first()
    )
    if not journey or not can_read_journey(user, journey):
        raise HTTPException(404, "Resource not found")
    step_row = (
        db.query(JourneyStep, PathwayStep)
        .join(PathwayStep, JourneyStep.pathway_step_id == PathwayStep.id)
        .filter(JourneyStep.id == step_id, JourneyStep.journey_id == journey_id)
        .with_for_update(of=JourneyStep)
        .first()
    )
    if not step_row:
        raise HTTPException(404, "Journey step not found")
    step, pathway_step = step_row
    if step.status not in {"READY", "IN_PROGRESS"}:
        raise HTTPException(
            409,
            f"Only READY or IN_PROGRESS steps can be completed; this step is {step.status}.",
        )

    owner_role = _check_step_completion_permission(db, journey, step, pathway_step, user)

    now = datetime.now(timezone.utc)
    step.status = "COMPLETED"
    step.completed_at = now
    step.block_reason = None
    step.updated_at = now
    db.add(
        PatientEvent(
            id=uuid4(),
            patient_id=journey.patient_id,
            journey_id=journey.id,
            event_type="STEP_COMPLETED",
            source="carepath-staff-ui",
            external_event_id=None,
            event_time=now,
            payload={
                "step_code": pathway_step.code,
                "journey_step_id": str(step.id),
                "owner_role": owner_role,
                "step_completed": True,
                "verified": True,
                "confirmed_by_user_id": str(user.id),
                "confirmed_by_role": user.role,
                "confirmation": "Staff confirmed the step was completed.",
            },
            processed=True,
            created_at=now,
        )
    )
    if owner_role == "PATIENT":
        for event in (
            db.query(PatientEvent)
            .filter(
                PatientEvent.journey_id == journey.id,
                PatientEvent.event_type == "PATIENT_STEP_SUBMITTED",
                PatientEvent.processed.is_(False),
                PatientEvent.payload["journey_step_id"].astext == str(step.id),
            )
            .all()
        ):
            event.processed = True
    JourneyRuleEngine(db).evaluate(journey.id)
    db.commit()
    return {
        "journey_id": str(journey.id),
        "step_id": str(step.id),
        "status": step.status,
        "completed_at": step.completed_at,
        "steps": steps_with_pathway_details(db, journey.id),
    }


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


@router.post("/journeys/{journey_id}/steps/{step_id}/evidence", status_code=201)
def add_step_evidence(
    journey_id: UUID,
    step_id: UUID,
    details: str = Form(default="", max_length=4000),
    evidence_type: str = Form(default="RESULT"),
    approval_confirmed: bool = Form(default=False),
    file: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
    user=Depends(require_staff),
):
    journey = get_journey_scoped(journey_id, db, user)
    step_row = (
        db.query(JourneyStep, PathwayStep)
        .join(PathwayStep, JourneyStep.pathway_step_id == PathwayStep.id)
        .filter(JourneyStep.id == step_id, JourneyStep.journey_id == journey_id)
        .first()
    )
    if not step_row:
        raise HTTPException(404, "Journey step not found")
    step, pathway_step = step_row
    if step.status not in {"READY", "IN_PROGRESS", "BLOCKED"}:
        raise HTTPException(409, "Evidence can only be added to an active journey step.")
    if evidence_type not in {"RESULT", "APPROVAL"}:
        raise HTTPException(422, "Evidence type must be RESULT or APPROVAL.")
    expected_evidence_type = (
        "APPROVAL"
        if step.block_reason == "Required approval evidence is missing"
        else "RESULT"
    )
    if step.status == "BLOCKED" and step.block_reason not in {
        "Required result evidence is missing",
        "Required approval evidence is missing",
    }:
        raise HTTPException(409, "This step is blocked for a reason that evidence submission cannot resolve.")
    if evidence_type != expected_evidence_type:
        raise HTTPException(409, "Evidence type does not match this step's current requirement.")
    if not details.strip() and file is None:
        raise HTTPException(422, "Enter evidence details or attach a file.")
    if evidence_type == "APPROVAL" and not approval_confirmed:
        raise HTTPException(422, "Confirm that the required approval has actually been received.")

    owner_role = str(step.owner_role or pathway_step.owner_role or "STAFF").upper()
    allowed_roles = {
        "CLINICIAN": {"CLINICIAN"},
        "CARE_COORDINATOR": {"CARE_COORDINATOR"},
        "ADMIN": {"ADMIN"},
        "STAFF": STAFF_ROLES,
    }
    if str(user.role).upper() not in allowed_roles.get(owner_role, set()):
        raise HTTPException(403, f"This step is assigned to {owner_role.lower().replace('_', ' ')} staff.")

    file_id = None
    file_name = None
    file_size = None
    if file is not None:
        try:
            file_id, file_name, file_size = save_evidence_file(file)
        except EvidenceFileError as exc:
            raise HTTPException(422, str(exc))
        finally:
            file.file.close()

    payload = {
        "journey_step_id": str(step.id),
        "step_code": pathway_step.code,
        "details": details.strip(),
    }
    event_type = "STEP_EVIDENCE_RECORDED"
    if evidence_type == "APPROVAL":
        payload["approved"] = True
        event_type = "STEP_APPROVAL_EVIDENCE_RECORDED"
    else:
        payload["result_available"] = True
    if file_id is not None:
        payload["file_id"] = str(file_id)
        payload["file_name"] = file_name
        payload["file_size_bytes"] = file_size
        payload["download_url"] = f"/api/v1/journeys/{journey_id}/steps/{step_id}/evidence/{file_id}"

    try:
        event, _ = EventProcessor(db).ingest(
            journey.id,
            event_type,
            "carepath-step-evidence",
            datetime.now(timezone.utc),
            payload,
        )
    except Exception:
        db.rollback()
        if file_id is not None:
            evidence_file_path(file_id).unlink(missing_ok=True)
        raise
    return {
        "event_id": str(event.id),
        "step_id": str(step.id),
        "status": db.query(JourneyStep).filter(JourneyStep.id == step.id).one().status,
        "file_name": file_name,
        "file_size_bytes": file_size,
    }


@router.get("/journeys/{journey_id}/steps/{step_id}/evidence/{file_id}")
def download_step_evidence(
    journey_id: UUID,
    step_id: UUID,
    file_id: UUID,
    db: Session = Depends(get_db),
    user=Depends(require_staff),
):
    get_journey_scoped(journey_id, db, user)
    event = (
        db.query(PatientEvent)
        .filter(
            PatientEvent.journey_id == journey_id,
            PatientEvent.event_type.in_(
                {"STEP_EVIDENCE_RECORDED", "STEP_APPROVAL_EVIDENCE_RECORDED"}
            ),
            PatientEvent.payload["journey_step_id"].astext == str(step_id),
            PatientEvent.payload["file_id"].astext == str(file_id),
        )
        .first()
    )
    if not event:
        raise HTTPException(404, "Evidence file not found")
    path = evidence_file_path(file_id)
    if not path.is_file():
        raise HTTPException(404, "Evidence file is missing from storage")
    return FileResponse(
        path,
        filename=Path(str(event.payload.get("file_name") or "evidence")).name,
        media_type="application/octet-stream",
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


@router.post("/journeys/{journey_id}/orchestrate", response_model=OrchestrationResponse)
def orchestrate(journey_id: UUID, db: Session = Depends(get_db), user=Depends(get_current_user)):
    # Patients can never orchestrate; staff must be in scope for this journey.
    journey = get_journey_for_action(journey_id, db, user, allowed_roles=STAFF_ROLES)
    try:
        result = SupervisorGraph(db).run(journey.id)
        return jsonable_encoder({
            "journey_id": journey.id,
            "status": result.get("status"),
            "decision": result.get("decision"),
            "result": result.get("result"),
            "outcomes": result.get("outcomes", []),
            "calls": result.get("calls", []),
            "run_id": result.get("run_id"),
            "summary": result.get("summary"),
            "mode": result.get("mode"),
            "warnings": result.get("warnings", []),
            "step_changes": result.get("step_changes", []),
            "journey_status": result.get("journey_status"),
        })
    except OrchestrationFailure as exc:
        raise HTTPException(502, str(exc))
    except Exception:
        db.rollback()
        raise HTTPException(502, "Orchestration failed unexpectedly. No changes were saved.")
