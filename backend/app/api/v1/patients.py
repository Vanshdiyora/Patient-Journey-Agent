from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.authorization import require_staff, scope_patient_ids
from app.models import Patient, Journey, Pathway, ExceptionRecord, User, StaffPatientAssignment
from app.schemas import PatientResponse, JourneyResponse
from app.schemas.journey import JourneyCreate
from app.services.journey_views import journey_with_pathway, journeys_with_pathways
from app.services.journey_service import ACTIVE_JOURNEY_STATUSES, start_journey_for_patient
from app.services.patient_search import patient_search_condition
from app.services.chat_service import audit

router = APIRouter()

# Role-relevant directory slices for the Patients page tabs. Each value narrows
# the directory by journey state; which tabs a role SEES is a UI concern, while
# the backend authorizes every request regardless.
VALID_FILTERS = ("active", "blocked", "has_exceptions", "high_priority", "mine")


def _apply_directory_filter(q, db: Session, filter_key: str | None):
    """Narrow the patient directory by journey/exception state via subquery."""
    if not filter_key:
        return q
    if filter_key == "active":
        sub = db.query(Journey.patient_id).filter(Journey.status == "ACTIVE")
        return q.filter(Patient.id.in_(sub))
    if filter_key == "blocked":
        sub = db.query(Journey.patient_id).filter(Journey.status == "BLOCKED")
        return q.filter(Patient.id.in_(sub))
    if filter_key == "high_priority":
        sub = db.query(Journey.patient_id).filter(
            Journey.status == "ACTIVE", Journey.priority.in_(("CRITICAL", "HIGH"))
        )
        return q.filter(Patient.id.in_(sub))
    if filter_key == "has_exceptions":
        sub = db.query(Journey.patient_id).join(
            ExceptionRecord, ExceptionRecord.journey_id == Journey.id
        ).filter(ExceptionRecord.status.in_(("OPEN", "IN_PROGRESS")))
        return q.filter(Patient.id.in_(sub))
    return q


@router.get("/patients")
def list_patients(
    search: str | None = None,
    filter: str | None = Query(None, description=f"One of: {', '.join(VALID_FILTERS)}"),
    limit: int = Query(10, ge=1, le=10),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user=Depends(require_staff),
):
    if filter and filter not in VALID_FILTERS:
        raise HTTPException(422, f"filter must be one of: {', '.join(VALID_FILTERS)}")
    if filter == "mine" and user.role != "CLINICIAN":
        raise HTTPException(422, "The My patients filter is for clinicians only")
    q = db.query(Patient)
    if user.role == "CLINICIAN":
        # All patients is a limited directory. Care filters show only patients
        # this clinician is responsible for; detail/journey routes stay scoped.
        if filter:
            q = q.filter(Patient.assigned_clinician_id == user.id)
        directory_scope = "directory" if not filter else "assigned"
    else:
        patient_ids = scope_patient_ids(db, user)
        if patient_ids is not None:
            q = q.filter(Patient.id.in_(patient_ids))
        directory_scope = "all" if patient_ids is None else "assigned"
    q = _apply_directory_filter(q, db, filter)
    if search:
        q = q.filter(patient_search_condition(search))
    total = q.order_by(None).count()
    rows = q.order_by(Patient.created_at.desc(), Patient.id.desc()).offset(offset).limit(limit).all()
    clinician_ids = {patient.assigned_clinician_id for patient in rows if patient.assigned_clinician_id}
    clinicians = {clinician.id: clinician.display_name for clinician in db.query(User).filter(User.id.in_(clinician_ids)).all()} if clinician_ids else {}
    items = []
    for patient in rows:
        item = PatientResponse.model_validate(patient).model_dump(mode="json")
        # Unassigned and other clinicians' patients appear in the directory,
        # without exposing contact details to a clinician who does not care for them.
        if user.role == "CLINICIAN" and patient.assigned_clinician_id != user.id:
            item["email"] = None
        item["assigned_clinician_name"] = clinicians.get(patient.assigned_clinician_id)
        items.append(item)
    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
        "filter": filter,
        "scope": directory_scope,
    }


@router.post("/patients/{patient_id}/claim")
def claim_patient(patient_id: UUID, db: Session = Depends(get_db), user=Depends(require_staff)):
    """Let a clinician claim one unassigned patient, without reassignment."""
    if user.role != "CLINICIAN":
        raise HTTPException(403, "Only a clinician can claim an unassigned patient")
    patient = db.query(Patient).filter(Patient.id == patient_id).with_for_update().first()
    if patient is None:
        raise HTTPException(404, "Patient not found")
    if patient.assigned_clinician_id is not None:
        raise HTTPException(409, "This patient already has an assigned clinician")
    patient.assigned_clinician_id = user.id
    db.add(StaffPatientAssignment(staff_user_id=user.id, patient_id=patient_id,
                                  assigned_by_user_id=user.id))
    audit(db, user=user, tool_name="claim_patient", event="executed",
          target_entity="patient", target_entity_id=patient_id,
          parameters={"patient_id": str(patient_id)}, correlation_id=uuid4(),
          result_status="success")
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "This patient could not be assigned. Reload and try again") from exc
    return {"patient_id": str(patient_id), "clinician_id": str(user.id), "assigned": True}


@router.get("/patients/{patient_id}", response_model=PatientResponse)
def get_patient(patient_id: UUID, db: Session = Depends(get_db), user=Depends(require_staff)):
    q = db.query(Patient).filter(Patient.id == patient_id)
    patient_ids = scope_patient_ids(db, user)
    if patient_ids is not None:
        q = q.filter(Patient.id.in_(patient_ids))
    item = q.first()
    if not item:
        raise HTTPException(404, "Patient not found")
    clinician_name = None
    if item.assigned_clinician_id:
        clinician_name = db.query(User.display_name).filter(User.id == item.assigned_clinician_id).scalar()
    return PatientResponse.model_validate(item).model_copy(update={"assigned_clinician_name": clinician_name})


@router.get("/patients/{patient_id}/journeys")
def patient_journeys(patient_id: UUID, limit: int = Query(10, ge=1, le=10), offset: int = Query(0, ge=0), db: Session = Depends(get_db), user=Depends(require_staff)):
    patient_ids = scope_patient_ids(db, user)
    if patient_ids is not None and patient_id not in patient_ids:
        raise HTTPException(404, "Patient not found")
    if not db.query(Patient).filter(Patient.id == patient_id).first():
        raise HTTPException(404, "Patient not found")
    q = db.query(Journey).filter(Journey.patient_id == patient_id)
    journeys = q.order_by(Journey.started_at.desc(), Journey.id.desc()).offset(offset).limit(limit).all()
    has_active_journey = q.filter(Journey.status.in_(ACTIVE_JOURNEY_STATUSES)).first() is not None
    return {"items": journeys_with_pathways(db, journeys), "total": q.count(), "limit": limit, "offset": offset,
            "has_active_journey": has_active_journey}


@router.post("/patients/{patient_id}/journeys", response_model=JourneyResponse, status_code=201)
def start_patient_journey(
    patient_id: UUID,
    data: JourneyCreate,
    db: Session = Depends(get_db),
    user=Depends(require_staff),
):
    if user.role not in {"ADMIN", "CLINICIAN"}:
        raise HTTPException(403, "Only an administrator or the assigned clinician can start a journey")
    # Lock the patient row so two requests cannot start active journeys for
    # this patient at the same time.
    patient = db.query(Patient).filter(Patient.id == patient_id).with_for_update().first()
    if not patient or (user.role == "CLINICIAN" and patient.assigned_clinician_id != user.id):
        raise HTTPException(404, "Patient not found")

    if user.role == "ADMIN":
        if data.priority is not None:
            raise HTTPException(422, "Administrators cannot set journey priority")
        priority = "MEDIUM"
    else:
        if data.priority is None:
            raise HTTPException(422, "Clinicians must set journey priority")
        priority = data.priority

    # All start paths share the same journey creation and active-journey rules.
    journey = start_journey_for_patient(
        db, patient_id, data.pathway_id, priority, data.step_time_limits_hours
    )
    pathway = db.query(Pathway).filter(Pathway.id == data.pathway_id).first()
    db.commit()
    db.refresh(journey)
    return journey_with_pathway(journey, pathway.name if pathway else None)
