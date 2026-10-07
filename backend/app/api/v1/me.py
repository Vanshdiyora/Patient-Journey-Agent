"""
Patient-scoped endpoints (/api/v1/me...).

Every handler resolves the patient from the authenticated user's DB record —
never from a request parameter — and verifies journey ownership before any read
or write. Event submissions are restricted: type allowlist, payload key
allowlist, server-set source ("patient-portal"), unverified by default.
"""
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.authorization import get_owned_patient, require_patient
from app.models import Journey, Patient, PatientEvent
from app.schemas.patient_event import (
    PATIENT_EVENT_TYPES,
    PATIENT_PAYLOAD_KEYS,
    PatientEventCreate,
    PatientEventResponse,
)
from app.schemas import JourneyResponse, JourneyStepResponse
from app.api.v1.journey_views import journeys_with_pathways, steps_with_pathway_details

router = APIRouter(prefix="/me", tags=["patient"])

PATIENT_SOURCE = "patient-portal"


def _own_journey(journey_id: UUID, db: Session, patient_id: UUID) -> Journey:
    journey = db.query(Journey).filter(Journey.id == journey_id).first()
    # 404 for other patients' journeys too: do not reveal existence.
    if not journey or journey.patient_id != patient_id:
        raise HTTPException(404, "Journey not found")
    return journey


@router.get("")
def my_profile(user=Depends(require_patient), db: Session = Depends(get_db)):
    patient_id = get_owned_patient(user)
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(404, "Patient record not found")
    return {
        "id": patient.id,
        "patient_reference": patient.patient_reference,
        "first_name": patient.first_name,
        "last_name": patient.last_name,
        "email": patient.email,
        "gender": patient.gender,
    }


@router.get("/journeys", response_model=list[JourneyResponse])
def my_journeys(user=Depends(require_patient), db: Session = Depends(get_db)):
    patient_id = get_owned_patient(user)
    journeys = (
        db.query(Journey)
        .filter(Journey.patient_id == patient_id)
        .order_by(Journey.started_at.desc())
        .all()
    )
    return journeys_with_pathways(db, journeys)


@router.get("/journeys/{journey_id}", response_model=JourneyResponse)
def my_journey(journey_id: UUID, user=Depends(require_patient), db: Session = Depends(get_db)):
    journey = _own_journey(journey_id, db, get_owned_patient(user))
    return journeys_with_pathways(db, [journey])[0]


@router.get("/journeys/{journey_id}/steps", response_model=list[JourneyStepResponse])
def my_journey_steps(journey_id: UUID, user=Depends(require_patient), db: Session = Depends(get_db)):
    journey = _own_journey(journey_id, db, get_owned_patient(user))
    return steps_with_pathway_details(db, journey.id)


@router.get("/journeys/{journey_id}/events", response_model=list[PatientEventResponse])
def my_journey_events(journey_id: UUID, user=Depends(require_patient), db: Session = Depends(get_db)):
    journey = _own_journey(journey_id, db, get_owned_patient(user))
    return (
        db.query(PatientEvent)
        .filter(PatientEvent.journey_id == journey.id)
        .order_by(PatientEvent.event_time.desc())
        .limit(100)
        .all()
    )


@router.post("/journeys/{journey_id}/events", response_model=PatientEventResponse, status_code=201)
def submit_patient_event(
    journey_id: UUID,
    data: PatientEventCreate,
    user=Depends(require_patient),
    db: Session = Depends(get_db),
):
    patient_id = get_owned_patient(user)
    journey = _own_journey(journey_id, db, patient_id)

    if data.event_type not in PATIENT_EVENT_TYPES:
        raise HTTPException(422, "Event type not permitted for patient submission")

    # Strip anything outside the allowlist; the server owns the rest.
    safe_payload = {k: v for k, v in (data.payload or {}).items() if k in PATIENT_PAYLOAD_KEYS}

    event = PatientEvent(
        id=uuid4(),
        patient_id=patient_id,
        journey_id=journey.id,
        event_type=data.event_type,
        source=PATIENT_SOURCE,
        event_time=datetime.now(timezone.utc),
        payload=safe_payload,
        processed=False,  # patient reports are reviewed, never auto-applied
        created_at=datetime.now(timezone.utc),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event
