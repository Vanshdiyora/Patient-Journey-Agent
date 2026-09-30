from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.authorization import require_staff, can_read_journey, scope_patient_ids
from app.models import Patient, Journey
from app.schemas import PatientResponse, JourneyResponse

router = APIRouter()


@router.get("/patients")
def list_patients(
    search: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user=Depends(require_staff),
):
    q = db.query(Patient)
    patient_ids = scope_patient_ids(db, user)
    if patient_ids is not None:
        q = q.filter(Patient.id.in_(patient_ids))
    if search:
        term = f"%{search}%"
        q = q.filter(
            Patient.patient_reference.ilike(term)
            | Patient.first_name.ilike(term)
            | Patient.last_name.ilike(term)
        )
    total = q.order_by(None).count()
    return {
        "items": q.order_by(Patient.created_at.desc()).offset(offset).limit(limit).all(),
        "total": total,
        "limit": limit,
        "offset": offset,
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


@router.get("/patients/{patient_id}/journeys", response_model=list[JourneyResponse])
def patient_journeys(patient_id: UUID, db: Session = Depends(get_db), user=Depends(require_staff)):
    if not db.query(Patient).filter(Patient.id == patient_id).first():
        raise HTTPException(404, "Patient not found")
    patient_ids = scope_patient_ids(db, user)
    if patient_ids is not None and patient_id not in patient_ids:
        raise HTTPException(404, "Patient not found")
    return (
        db.query(Journey)
        .filter(Journey.patient_id == patient_id)
        .order_by(Journey.started_at.desc())
        .all()
    )
