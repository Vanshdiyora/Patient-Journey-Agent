from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.authorization import (
    STAFF_ROLES,
    get_journey_for_action,
    get_journey_scoped,
    require_staff,
)
from app.models import Journey, PatientEvent
from app.schemas import EventCreate, EventResponse
from app.orchestration.event_processor import EventProcessor

router = APIRouter()

STEP_COMPLETION_EVENT_TYPES = {
    "STEP_COMPLETED",
    "FOLLOWUP_COMPLETED",
    "APPOINTMENT_COMPLETED",
    "LAB_RESULT_AVAILABLE",
    "DISCHARGE_COMPLETED",
}


@router.get("/journeys/{journey_id}/events", response_model=list[EventResponse])
def events(journey_id: UUID, limit: int = 100, db: Session = Depends(get_db), user=Depends(require_staff)):
    get_journey_scoped(journey_id, db, user)
    return (
        db.query(PatientEvent)
        .filter(PatientEvent.journey_id == journey_id)
        .order_by(PatientEvent.event_time.desc())
        .limit(min(max(limit, 1), 500))
        .all()
    )


@router.post("/journeys/{journey_id}/events", response_model=EventResponse, status_code=201)
def add_event(journey_id: UUID, data: EventCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    # ADMIN/CLINICIAN/CARE_COORDINATOR may submit operational/staff events;
    # the server decides verified — clients cannot set it for step completion.
    journey = get_journey_for_action(journey_id, db, user, allowed_roles=STAFF_ROLES)
    if data.source in {"carepath-ui-patient", "patient-portal", "patient"}:
        raise HTTPException(403, "Patient-channel sources are reserved for patient APIs")
    if (
        data.event_type in STEP_COMPLETION_EVENT_TYPES
        or "verified" in data.payload
        or data.payload.get("step_completed") is True
    ):
        raise HTTPException(
            422,
            "Step completion must be recorded with the staff-only complete-step action.",
        )
    try:
        event, _result = EventProcessor(db).ingest(
            journey.id, data.event_type, data.source, data.event_time, data.payload, data.external_event_id
        )
        return event
    except ValueError as exc:
        db.rollback()
        raise HTTPException(404, str(exc))
