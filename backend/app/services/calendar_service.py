"""Calendar projections and bookings over the existing journey step records.

Every query starts from the authenticated user's patient scope. Clinical
completion and cancellation are read from the live journey, never copied.
"""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import DateTime, and_, case, func, or_, text

from app.core.authorization import STAFF_ROLES, scope_patient_ids
from app.models import Journey, JourneyStep, Patient, PatientEvent, Pathway, PathwayStep, StaffPatientAssignment, User


def utc(value):
    # SQLite test fixtures return naive timestamps; PostgreSQL uses TIMESTAMPTZ.
    return value.replace(tzinfo=timezone.utc) if value and value.tzinfo is None else value


def calendar_query(db, user):
    q = (db.query(JourneyStep, Journey, PathwayStep, Patient, Pathway)
         .join(Journey, Journey.id == JourneyStep.journey_id)
         .join(PathwayStep, PathwayStep.id == JourneyStep.pathway_step_id)
         .join(Patient, Patient.id == Journey.patient_id)
         .join(Pathway, Pathway.id == Journey.pathway_id))
    ids = scope_patient_ids(db, user)
    return q if ids is None else q.filter(Patient.id.in_(ids))


def calendar_dates(db):
    """SQL expressions keep range filtering and pagination in the database."""
    if db.get_bind().dialect.name == "sqlite":
        planned = func.datetime(Journey.started_at, func.printf("%+d days", PathwayStep.due_after_days), type_=DateTime())
    else:
        planned = Journey.started_at + PathwayStep.due_after_days * text("INTERVAL '1 day'")
    planned = case((PathwayStep.due_after_days.is_not(None), planned), else_=None)
    start = func.coalesce(JourneyStep.scheduled_start_at, JourneyStep.due_at, planned, JourneyStep.completed_at)
    if db.get_bind().dialect.name == "sqlite":
        next_day = func.datetime(start, "+1 day", type_=DateTime())
    else:
        next_day = start + text("INTERVAL '1 day'")
    end = func.coalesce(JourneyStep.scheduled_end_at, JourneyStep.due_at, next_day)
    return start, end


def calendar_status(start, end, now):
    return case(
        (JourneyStep.status == "COMPLETED", "COMPLETED"),
        (or_(Journey.status == "CANCELLED", JourneyStep.status == "CANCELLED", JourneyStep.schedule_status == "CANCELLED"), "CANCELLED"),
        (end < now, "OVERDUE"),
        (JourneyStep.schedule_status == "RESCHEDULED", "RESCHEDULED"),
        else_="UPCOMING",
    )


def assigned_staff(db, patients):
    """Canonical clinician links plus explicit coordination assignments."""
    by_patient = {p.id: [] for p in patients}
    patient_ids = list(by_patient)
    if not patient_ids:
        return by_patient
    clinician_ids = {p.assigned_clinician_id for p in patients if p.assigned_clinician_id}
    clinicians = {u.id: u for u in db.query(User).filter(User.id.in_(clinician_ids), User.role == "CLINICIAN").all()} if clinician_ids else {}
    for p in patients:
        if p.assigned_clinician_id in clinicians:
            by_patient[p.id].append(clinicians[p.assigned_clinician_id])
    rows = (db.query(StaffPatientAssignment.patient_id, User)
            .join(User, User.id == StaffPatientAssignment.staff_user_id)
            .filter(StaffPatientAssignment.patient_id.in_(patient_ids), User.role == "CARE_COORDINATOR")
            .order_by(User.display_name, User.id).all())
    for patient_id, staff in rows:
        by_patient[patient_id].append(staff)
    return by_patient


def staff_summary(staff):
    return {"id": str(staff.id), "name": staff.display_name, "role": staff.role, "is_active": staff.is_active}


def event_dates(row):
    step, journey, template, _, _ = row
    planned = utc(journey.started_at) + timedelta(days=template.due_after_days) if template.due_after_days is not None else None
    start = utc(step.scheduled_start_at) or utc(step.due_at) or planned or utc(step.completed_at)
    end = utc(step.scheduled_end_at) or utc(step.due_at) or (start + timedelta(days=1) if start else None)
    return start, end


def serialize_events(db, user, rows):
    if not rows:
        return []
    patients = {row[3].id: row[3] for row in rows}
    staff_by_patient = assigned_staff(db, list(patients.values()))
    booked_staff_ids = {row[0].scheduled_staff_id for row in rows if row[0].scheduled_staff_id}
    booked_staff = {u.id: u for u in db.query(User).filter(User.id.in_(booked_staff_ids)).all()} if booked_staff_ids else {}
    journey_ids = {row[1].id for row in rows}
    progress = {jid: {"completed": 0, "total": 0, "pending": 0} for jid in journey_ids}
    for jid, status, count in (db.query(JourneyStep.journey_id, JourneyStep.status, func.count(JourneyStep.id))
                              .filter(JourneyStep.journey_id.in_(journey_ids))
                              .group_by(JourneyStep.journey_id, JourneyStep.status).all()):
        progress[jid]["total"] += count
        if status == "COMPLETED":
            progress[jid]["completed"] += count
        elif status != "CANCELLED":
            progress[jid]["pending"] += count

    # Conflict hints use only visible patients and never return another event's
    # patient identity. The write guard below checks availability system-wide.
    dated = [event_dates(row) for row in rows]
    starts = [start for start, _ in dated if start]
    ends = [end for _, end in dated if end]
    overlaps = []
    if starts and ends:
        overlaps = (calendar_query(db, user)
                    .filter(JourneyStep.scheduled_start_at < max(ends), JourneyStep.scheduled_end_at > min(starts),
                            JourneyStep.schedule_status != "CANCELLED", JourneyStep.status.notin_(("COMPLETED", "CANCELLED")),
                            Journey.status.notin_(("COMPLETED", "CANCELLED"))).all())
    now = datetime.now(timezone.utc)
    items = []
    for row, (start, end) in zip(rows, dated):
        step, journey, template, patient, pathway = row
        booked = step.scheduled_start_at is not None
        if step.status == "COMPLETED":
            status = "COMPLETED"
        elif journey.status == "CANCELLED" or step.status == "CANCELLED" or step.schedule_status == "CANCELLED":
            status = "CANCELLED"
        elif end and end < now:
            status = "OVERDUE"
        else:
            status = "RESCHEDULED" if step.schedule_status == "RESCHEDULED" else "UPCOMING"
        conflicts = 0
        if booked and status not in {"COMPLETED", "CANCELLED"}:
            for other in overlaps:
                other_step, other_journey = other[:2]
                if (other_step.id != step.id and utc(other_step.scheduled_start_at) < end
                        and utc(other_step.scheduled_end_at) > start
                        and (other_journey.patient_id == patient.id or
                             (step.scheduled_staff_id and step.scheduled_staff_id == other_step.scheduled_staff_id))):
                    conflicts += 1
        items.append({
            "id": str(step.id), "patient_id": str(patient.id),
            "patient_name": f"{patient.first_name} {patient.last_name}", "patient_reference": patient.patient_reference,
            "journey_id": str(journey.id), "journey_name": pathway.name,
            "journey_status": journey.status, "journey_progress": progress[journey.id],
            "activity": template.name, "activity_type": template.step_type,
            "description": template.description, "step_status": step.status,
            "owner_role": step.owner_role or template.owner_role,
            "starts_at": start, "ends_at": end, "all_day": not booked,
            "date_source": "BOOKING" if booked else "DEADLINE" if step.due_at else "PATHWAY_PLAN",
            "status": status, "schedule_status": step.schedule_status,
            "assigned_staff": staff_summary(booked_staff[step.scheduled_staff_id]) if step.scheduled_staff_id in booked_staff else None,
            "care_team": [staff_summary(u) for u in staff_by_patient[patient.id]],
            "revision": step.schedule_revision, "conflict_count": conflicts,
            "can_manage": user.role in STAFF_ROLES and step.status not in {"COMPLETED", "CANCELLED"} and journey.status not in {"COMPLETED", "CANCELLED"},
        })
    return items


def get_calendar_event(db, user, step_id):
    row = calendar_query(db, user).filter(JourneyStep.id == step_id).first()
    if row is None:
        raise HTTPException(404, "Calendar activity not found")
    return row


def lock_activity(db, user, step_id, revision):
    if user.role not in STAFF_ROLES:
        raise HTTPException(403, "Only assigned staff can manage scheduling")
    row = get_calendar_event(db, user, step_id)
    # Match the journey-before-step locking order used by clinical completion.
    db.query(Journey).filter(Journey.id == row[1].id).with_for_update().populate_existing().one()
    db.query(Patient).filter(Patient.id == row[3].id).with_for_update().populate_existing().one()
    # Reapply assignments after acquiring locks; a grant may have been removed.
    row = get_calendar_event(db, user, step_id)
    if user.role == "CARE_COORDINATOR":
        grant = (db.query(StaffPatientAssignment).filter(
            StaffPatientAssignment.staff_user_id == user.id,
            StaffPatientAssignment.patient_id == row[3].id,
        ).with_for_update().first())
        if grant is None:
            raise HTTPException(404, "Calendar activity not found")
    step = db.query(JourneyStep).filter(JourneyStep.id == step_id).with_for_update().populate_existing().one()
    if step.status in {"COMPLETED", "CANCELLED"} or row[1].status in {"COMPLETED", "CANCELLED"}:
        raise HTTPException(409, "Completed or cancelled journey activities cannot be scheduled")
    if step.schedule_revision != revision:
        raise HTTPException(409, "This schedule changed. Reload the activity before saving")
    return row


def validate_booking(db, row, data):
    step, _, _, patient, _ = row
    if data.assigned_staff_id:
        # Serialize bookings for a staff member, including different patients.
        staff = (db.query(User).filter(User.id == data.assigned_staff_id)
                 .with_for_update().populate_existing().first())
        allowed = assigned_staff(db, [patient])[patient.id]
        if staff is None or not staff.is_active or staff.id not in {u.id for u in allowed}:
            raise HTTPException(422, "Choose an active clinician or care coordinator assigned to this patient")
        if staff.role == "CARE_COORDINATOR":
            grant = (db.query(StaffPatientAssignment).filter(
                StaffPatientAssignment.staff_user_id == staff.id,
                StaffPatientAssignment.patient_id == patient.id,
            ).with_for_update().first())
            if grant is None:
                raise HTTPException(422, "Choose staff currently assigned to this patient")
    conflict = (db.query(JourneyStep.id).join(Journey, Journey.id == JourneyStep.journey_id)
                .filter(JourneyStep.id != step.id, JourneyStep.scheduled_start_at < data.ends_at,
                        JourneyStep.scheduled_end_at > data.starts_at,
                        JourneyStep.schedule_status != "CANCELLED",
                        JourneyStep.status.notin_(("COMPLETED", "CANCELLED")),
                        Journey.status.notin_(("COMPLETED", "CANCELLED")),
                        or_(Journey.patient_id == patient.id,
                            and_(JourneyStep.scheduled_staff_id == data.assigned_staff_id,
                                 JourneyStep.scheduled_staff_id.is_not(None))))
                .first())
    if conflict:
        # Do not disclose the patient, journey, event ID, or staff in a conflict.
        raise HTTPException(409, "The patient or selected staff member is unavailable during this time")


def record_schedule_change(db, user, row, action, before):
    step, journey = row[:2]
    now = datetime.now(timezone.utc)
    step.schedule_revision += 1
    step.updated_at = now
    journey.updated_at = now
    db.add(PatientEvent(
        id=uuid4(), patient_id=journey.patient_id, journey_id=journey.id,
        event_type=action, source="calendar", event_time=now, processed=True, created_at=now,
        payload={"journey_step_id": str(step.id), "confirmed_by_user_id": str(user.id),
                 "confirmed_by_role": user.role, "before": before, "after": schedule_snapshot(step)},
    ))


def schedule_snapshot(step):
    return {"starts_at": utc(step.scheduled_start_at).isoformat() if step.scheduled_start_at else None,
            "ends_at": utc(step.scheduled_end_at).isoformat() if step.scheduled_end_at else None,
            "assigned_staff_id": str(step.scheduled_staff_id) if step.scheduled_staff_id else None,
            "status": step.schedule_status, "revision": step.schedule_revision}
