"""Role-scoped calendar reads and confirmed scheduling changes."""
from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import AwareDatetime
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.core.authorization import require_staff, scope_patient_ids
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models import Journey, JourneyStep, Patient, Pathway, PathwayStep, StaffPatientAssignment, User
from app.schemas.calendar import CalendarBooking, CalendarConfirmation, CalendarCreate
from app.services.calendar_service import (
    assigned_staff, calendar_dates, calendar_query, calendar_status, get_calendar_event,
    lock_activity, record_schedule_change, schedule_snapshot, serialize_events, staff_summary, utc, validate_booking,
)
from app.services.patient_search import patient_search_condition

router = APIRouter(prefix="/calendar", tags=["calendar"])


@router.get("/events")
def list_calendar_events(
    start: AwareDatetime,
    end: AwareDatetime,
    search: str | None = Query(None, max_length=200),
    patient_id: UUID | None = None,
    clinician_id: UUID | None = None,
    coordinator_id: UUID | None = None,
    journey_status: Literal["ACTIVE", "BLOCKED", "COMPLETED", "CANCELLED"] | None = None,
    status: Literal["UPCOMING", "OVERDUE", "COMPLETED", "RESCHEDULED", "CANCELLED"] | None = None,
    limit: int = Query(500, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    start, end = start.astimezone(timezone.utc), end.astimezone(timezone.utc)
    if end <= start or end - start > timedelta(days=93):
        raise HTTPException(422, "Choose a date range between one instant and 93 days")
    q = calendar_query(db, user)
    begins, finishes = calendar_dates(db)
    q = q.filter(begins < end, or_(and_(JourneyStep.scheduled_start_at.is_not(None), finishes > start),
                                  and_(JourneyStep.scheduled_start_at.is_(None), begins >= start)))
    if patient_id:
        q = q.filter(Patient.id == patient_id)
    if clinician_id:
        q = q.filter(Patient.assigned_clinician_id == clinician_id)
    if coordinator_id:
        assigned = (db.query(StaffPatientAssignment.patient_id).join(User, User.id == StaffPatientAssignment.staff_user_id)
                    .filter(User.id == coordinator_id, User.role == "CARE_COORDINATOR"))
        q = q.filter(Patient.id.in_(assigned))
    if journey_status:
        q = q.filter(Journey.status == journey_status)
    if status:
        q = q.filter(calendar_status(begins, finishes, datetime.now(timezone.utc)) == status)
    if search and search.strip():
        term = f"%{' '.join(search.split())}%"
        q = q.filter(or_(patient_search_condition(search), PathwayStep.name.ilike(term), Pathway.name.ilike(term)))
    total = q.order_by(None).count()
    rows = q.order_by(begins, JourneyStep.id).offset(offset).limit(limit).all()
    return {"items": serialize_events(db, user, rows), "total": total, "limit": limit, "offset": offset}


@router.get("/options")
def calendar_options(patient_id: UUID | None = None, db: Session = Depends(get_db), user=Depends(get_current_user)):
    q = db.query(Patient)
    ids = scope_patient_ids(db, user)
    if ids is not None:
        q = q.filter(Patient.id.in_(ids))
    if patient_id:
        q = q.filter(Patient.id == patient_id)
    patients = q.order_by(Patient.first_name, Patient.last_name, Patient.id).all()
    if patient_id and not patients:
        raise HTTPException(404, "Patient not found")
    staff = assigned_staff(db, patients)
    staff_options = {}
    for p in patients:
        for member in staff[p.id]:
            option = staff_options.setdefault(member.id, {**staff_summary(member), "patient_ids": []})
            option["patient_ids"].append(str(p.id))
    activities = []
    if patient_id:
        for step, journey, template, _, pathway in calendar_query(db, user).filter(Patient.id == patient_id).order_by(Journey.started_at.desc(), PathwayStep.sequence_number).all():
            if journey.status not in {"COMPLETED", "CANCELLED"} and step.status not in {"COMPLETED", "CANCELLED"}:
                activities.append({"id": str(step.id), "name": template.name, "journey_name": pathway.name,
                                   "journey_id": str(journey.id), "step_status": step.status,
                                   "revision": step.schedule_revision, "booked": step.scheduled_start_at is not None})
    return {"patients": [{"id": str(p.id), "name": f"{p.first_name} {p.last_name}", "reference": p.patient_reference} for p in patients],
            "staff": list(staff_options.values()), "activities": activities}


@router.get("/events/{step_id}")
def calendar_event(step_id: UUID, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return serialize_events(db, user, [get_calendar_event(db, user, step_id)])[0]


def save_booking(db, user, row, data, creating=False):
    step = row[0]
    if creating and step.scheduled_start_at is not None:
        raise HTTPException(409, "This activity already has a booking. Open it to update the schedule")
    if not creating and step.scheduled_start_at is None:
        raise HTTPException(409, "Create a booking for this activity first")
    validate_booking(db, row, data)
    before = schedule_snapshot(step)
    changed_time = utc(step.scheduled_start_at) != data.starts_at or utc(step.scheduled_end_at) != data.ends_at
    step.scheduled_start_at, step.scheduled_end_at = data.starts_at, data.ends_at
    step.scheduled_staff_id = data.assigned_staff_id
    if creating:
        step.schedule_status = "SCHEDULED"
    elif changed_time or step.schedule_status == "CANCELLED":
        step.schedule_status = "RESCHEDULED"
    record_schedule_change(db, user, row, "SCHEDULE_CREATED" if creating else "SCHEDULE_UPDATED", before)
    db.commit()
    return serialize_events(db, user, [get_calendar_event(db, user, step.id)])[0]


@router.post("/events", status_code=201)
def create_calendar_event(data: CalendarCreate, db: Session = Depends(get_db), user=Depends(require_staff)):
    row = lock_activity(db, user, data.journey_step_id, data.revision)
    return save_booking(db, user, row, data, creating=True)


@router.patch("/events/{step_id}")
def update_calendar_event(step_id: UUID, data: CalendarBooking, db: Session = Depends(get_db), user=Depends(require_staff)):
    row = lock_activity(db, user, step_id, data.revision)
    return save_booking(db, user, row, data)


@router.post("/events/{step_id}/cancel")
def cancel_calendar_event(step_id: UUID, data: CalendarConfirmation, db: Session = Depends(get_db), user=Depends(require_staff)):
    row = lock_activity(db, user, step_id, data.revision)
    step = row[0]
    if step.scheduled_start_at is None or step.schedule_status == "CANCELLED":
        raise HTTPException(409, "There is no active booking to cancel")
    before = schedule_snapshot(step)
    step.schedule_status = "CANCELLED"
    record_schedule_change(db, user, row, "SCHEDULE_CANCELLED", before)
    db.commit()
    return serialize_events(db, user, [get_calendar_event(db, user, step_id)])[0]
