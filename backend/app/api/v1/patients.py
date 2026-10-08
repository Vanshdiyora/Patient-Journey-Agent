from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.authorization import require_staff, scope_patient_ids
from app.models import Patient, Journey, Pathway, ExceptionRecord
from app.schemas import PatientResponse, JourneyResponse
from app.schemas.journey import JourneyCreate
from app.api.v1.journey_views import journey_with_pathway, journeys_with_pathways
from app.services.journey_service import start_journey_for_patient

router = APIRouter()

# Role-relevant directory slices for the Patients page tabs. Each value narrows
# the directory by journey state; which tabs a role SEES is a UI concern, while
# the backend authorizes every request regardless.
VALID_FILTERS = ("active", "blocked", "has_exceptions", "high_priority")


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
    q = db.query(Patient)
    patient_ids = scope_patient_ids(db, user)
    if patient_ids is not None:
        q = q.filter(Patient.id.in_(patient_ids))
    q = _apply_directory_filter(q, db, filter)
    if search:
        term = f"%{search}%"
        q = q.filter(
            Patient.patient_reference.ilike(term)
            | Patient.first_name.ilike(term)
            | Patient.last_name.ilike(term)
        )
    total = q.order_by(None).count()
    return {
        "items": q.order_by(Patient.created_at.desc(), Patient.id.desc()).offset(offset).limit(limit).all(),
        "total": total,
        "limit": limit,
        "offset": offset,
        "filter": filter,
        "scope": "all" if patient_ids is None else "assigned",
    }


@router.get("/patients/{patient_id}", response_model=PatientResponse)
def get_patient(patient_id: UUID, db: Session = Depends(get_db), user=Depends(require_staff)):
    item = db.query(Patient).filter(Patient.id == patient_id).first()
    if not item:
        raise HTTPException(404, "Patient not found")
    # A patient record is readable if any of its journeys would be — approximate
    # scope check via patient id scope, since Patient has no journey link here.
    patient_ids = scope_patient_ids(db, user)
    if patient_ids is not None and item.id not in patient_ids:
        raise HTTPException(404, "Patient not found")
    return item


@router.get("/patients/{patient_id}/journeys")
def patient_journeys(patient_id: UUID, limit: int = Query(10, ge=1, le=10), offset: int = Query(0, ge=0), db: Session = Depends(get_db), user=Depends(require_staff)):
    if not db.query(Patient).filter(Patient.id == patient_id).first():
        raise HTTPException(404, "Patient not found")
    patient_ids = scope_patient_ids(db, user)
    if patient_ids is not None and patient_id not in patient_ids:
        raise HTTPException(404, "Patient not found")
    q = db.query(Journey).filter(Journey.patient_id == patient_id)
    journeys = q.order_by(Journey.started_at.desc(), Journey.id.desc()).offset(offset).limit(limit).all()
    return {"items": journeys_with_pathways(db, journeys), "total": q.count(), "limit": limit, "offset": offset}


@router.post("/patients/{patient_id}/journeys", response_model=JourneyResponse, status_code=201)
def start_patient_journey(
    patient_id: UUID,
    data: JourneyCreate,
    db: Session = Depends(get_db),
    user=Depends(require_staff),
):
    # Lock the patient row so two staff requests cannot start the same active
    # pathway for this patient at the same time.
    patient = db.query(Patient).filter(Patient.id == patient_id).with_for_update().first()
    patient_ids = scope_patient_ids(db, user)
    if not patient or (patient_ids is not None and patient_id not in patient_ids):
        raise HTTPException(404, "Patient not found")

    # Identical business rules as the chatbot's start_pathway tool: both call
    # the shared service so neither path can drift from the other.
    journey = start_journey_for_patient(
        db, patient_id, data.pathway_id, data.priority, data.step_time_limits_hours
    )
    pathway = db.query(Pathway).filter(Pathway.id == data.pathway_id).first()
    db.commit()
    db.refresh(journey)
    return journey_with_pathway(journey, pathway.name if pathway else None)
