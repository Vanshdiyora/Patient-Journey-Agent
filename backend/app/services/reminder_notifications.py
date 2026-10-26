from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models import InAppNotification, Journey, Patient, StaffPatientAssignment, User


def create_journey_reminder_notifications(
    db: Session,
    journey_id,
    payload: dict,
) -> dict:
    journey = db.query(Journey).filter(Journey.id == journey_id).first()
    if not journey:
        return {"accepted": False, "status": "NO_RECIPIENT", "reason": "The journey could not be found."}

    patient = db.query(Patient).filter(Patient.id == journey.patient_id).first()
    patient_user = (
        db.query(User)
        .filter(User.patient_id == journey.patient_id, User.role == "PATIENT", User.is_active.is_(True))
        .first()
    )
    if not patient or not patient_user:
        return {
            "accepted": False,
            "status": "NO_RECIPIENT",
            "reason": "The patient does not have an active portal account.",
        }

    recipients = {patient_user.id: patient_user}
    staff_users = (
        db.query(User)
        .filter(User.role == "ADMIN", User.is_active.is_(True))
        .all()
    )
    if patient.assigned_clinician_id:
        clinician = (
            db.query(User)
            .filter(
                User.id == patient.assigned_clinician_id,
                User.role == "CLINICIAN",
                User.is_active.is_(True),
            )
            .first()
        )
        if clinician:
            staff_users.append(clinician)

    coordinators = (
        db.query(User)
        .join(StaffPatientAssignment, StaffPatientAssignment.staff_user_id == User.id)
        .filter(
            StaffPatientAssignment.patient_id == journey.patient_id,
            User.role == "CARE_COORDINATOR",
            User.is_active.is_(True),
        )
        .all()
    )
    for user in (*staff_users, *coordinators):
        recipients[user.id] = user

    step_name = payload.get("step_name") or "your care plan"
    now = datetime.now(timezone.utc)
    patient_body = (
        f"This is a reminder about: {step_name}. "
        "Please review your care plan or contact your care team if you need help."
    )
    staff_body = (
        f"A care reminder was triggered for {patient.first_name} {patient.last_name} "
        f"about: {step_name}."
    )
    for user in recipients.values():
        db.add(
            InAppNotification(
                id=uuid4(),
                user_id=user.id,
                journey_id=journey.id,
                notification_type="JOURNEY_REMINDER",
                title="Care journey reminder" if user.role == "PATIENT" else "Patient reminder triggered",
                body=patient_body if user.role == "PATIENT" else staff_body,
                created_at=now,
                read_at=None,
            )
        )
    db.flush()

    return {
        "accepted": True,
        "status": "NOTIFICATION_CREATED",
        "delivery": "in_app",
        "notifications_created": len(recipients),
    }
