from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.authorization import require_staff, scope_patient_ids
from app.models import Journey, JourneyStep, ExceptionRecord, ActionExecution, Patient
from app.models.user import User

router = APIRouter()


@router.get("/dashboard/summary")
def dashboard(db: Session = Depends(get_db), user=Depends(require_staff)):
    c = lambda q: q.scalar() or 0  # noqa: E731

    patient_ids = scope_patient_ids(db, user)

    if patient_ids is None:
        journeys_active = db.query(Journey).filter(Journey.status == "ACTIVE")
        journeys_blocked = db.query(Journey).filter(Journey.status == "BLOCKED")
        journeys_completed = db.query(Journey).filter(Journey.status == "COMPLETED")
        exc_q = db.query(ExceptionRecord)
        steps_q = db.query(JourneyStep)
        actions_q = db.query(ActionExecution)
        patients_q = db.query(Patient)
    else:
        journeys_active = db.query(Journey).filter(Journey.patient_id.in_(patient_ids), Journey.status == "ACTIVE")
        journeys_blocked = db.query(Journey).filter(Journey.patient_id.in_(patient_ids), Journey.status == "BLOCKED")
        journeys_completed = db.query(Journey).filter(Journey.patient_id.in_(patient_ids), Journey.status == "COMPLETED")
        exc_q = db.query(ExceptionRecord).join(Journey, Journey.id == ExceptionRecord.journey_id).filter(Journey.patient_id.in_(patient_ids))
        steps_q = db.query(JourneyStep).join(Journey, Journey.id == JourneyStep.journey_id).filter(Journey.patient_id.in_(patient_ids))
        actions_q = db.query(ActionExecution).join(Journey, Journey.id == ActionExecution.journey_id).filter(Journey.patient_id.in_(patient_ids))
        patients_q = db.query(Patient).filter(Patient.id.in_(patient_ids))

    summary = {
        "active_journeys": c(journeys_active.with_entities(func.count(Journey.id))),
        "blocked_journeys": c(journeys_blocked.with_entities(func.count(Journey.id))),
        "completed_journeys": c(journeys_completed.with_entities(func.count(Journey.id))),
        "critical_exceptions": c(exc_q.with_entities(func.count(ExceptionRecord.id)).filter(ExceptionRecord.severity == "CRITICAL")),
        "open_exceptions": c(exc_q.with_entities(func.count(ExceptionRecord.id)).filter(ExceptionRecord.status == "OPEN")),
        "pending_steps": c(steps_q.with_entities(func.count(JourneyStep.id)).filter(JourneyStep.status.in_(["PENDING", "READY", "IN_PROGRESS"]))),
        "failed_actions": c(actions_q.with_entities(func.count(ActionExecution.id)).filter(ActionExecution.status == "FAILED")),
        "total_patients": c(patients_q.with_entities(func.count(Patient.id))),
        "scope": "all" if patient_ids is None else "assigned",
        "role": user.role,
    }

    # Admin-only identity metrics (the users table is an admin concern).
    if user.role == "ADMIN":
        summary["total_users"] = c(db.query(func.count(User.id)))
        summary["active_users"] = c(db.query(func.count(User.id)).filter(User.is_active.is_(True)))
        summary["patient_users"] = c(db.query(func.count(User.id)).filter(User.role == "PATIENT"))

    return summary
