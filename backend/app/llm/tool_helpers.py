"""
Shared building blocks for the chatbot tools: error types, argument
validators (LLM output is untrusted) and serializers.
"""
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.authorization import STAFF_ROLES, get_journey_scoped, scope_patient_ids
from app.models import Journey, JourneyStep, Patient, Pathway, PathwayStep


class ToolValidationError(Exception):
    """LLM-proposed arguments are invalid or the target was not found. The
    message is fed back to the model so it can correct itself or ask the user."""


class ToolPermissionError(Exception):
    """The user's role/scope does not allow this task. Reported to the user
    verbatim as "you are not permitted", never retried by the model."""


# ---------------------------------------------------------------------------
# Parameter validation
# ---------------------------------------------------------------------------

def require_dict(args: Any) -> dict[str, Any]:
    if not isinstance(args, dict):
        raise ToolValidationError("Tool arguments must be a JSON object")
    return args


def is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, dict)):
        return not value
    return False


def enum_value(value: Any, allowed: tuple[str, ...], field: str) -> str:
    if not isinstance(value, str) or value.strip().upper() not in allowed:
        raise ToolValidationError(f"{field} must be one of: {', '.join(allowed)}")
    return value.strip().upper()


def uuid_value(value: Any, field: str) -> UUID:
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        raise ToolValidationError(f"{field} must be a valid id")


def text_value(value: Any, field: str, *, max_len: int = 2000) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ToolValidationError(f"{field} must be non-empty text")
    return value.strip()[:max_len]


def int_value(value: Any, field: str, lo: int, hi: int) -> int:
    if isinstance(value, str) and value.strip().isdigit():
        value = int(value.strip())
    if isinstance(value, bool) or not isinstance(value, int):
        raise ToolValidationError(f"{field} must be an integer")
    if not lo <= value <= hi:
        raise ToolValidationError(f"{field} must be between {lo} and {hi}")
    return value


def bool_value(value: Any, field: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().lower() in ("true", "false"):
        return value.strip().lower() == "true"
    raise ToolValidationError(f"{field} must be true or false")


# ---------------------------------------------------------------------------
# Scope helpers
# ---------------------------------------------------------------------------

def staff_required(user) -> None:
    if user.role not in STAFF_ROLES:
        raise ToolPermissionError("Only care team members can use this action")


def patient_by_id(db: Session, patient_id: UUID) -> Patient | None:
    return db.query(Patient).filter(Patient.id == patient_id).first()


def patient_in_scope(db: Session, user, patient_id: UUID) -> Patient:
    """Patient row the user may read, else ToolValidationError (404-equivalent)."""
    ids = scope_patient_ids(db, user)
    if ids is not None and patient_id not in ids:
        raise ToolValidationError("Patient not found in your scope")
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise ToolValidationError("Patient not found")
    return patient


def target_patient_id(db: Session, user, args: dict[str, Any]) -> UUID:
    """Staff pass patient_id; patients are pinned to their own record."""
    if user.role == "PATIENT":
        if not user.patient_id:
            raise ToolPermissionError("Your account is not linked to a patient record")
        return user.patient_id
    raw = args.get("patient_id")
    if raw is None:
        raise ToolValidationError("patient_id is required")
    patient_id = uuid_value(raw, "patient_id")
    ids = scope_patient_ids(db, user)
    if ids is not None and patient_id not in ids:
        raise ToolValidationError("Patient not found in your scope")
    return patient_id


def readable_journey(db: Session, user, journey_id: UUID) -> Journey:
    """Journey the user may read; anything else reads as 'not found' so
    existence is never leaked across patients."""
    try:
        return get_journey_scoped(journey_id, db, user)
    except HTTPException as exc:
        raise ToolValidationError("Journey not found") from exc


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def patient_name(p: Patient | None) -> str | None:
    return f"{p.first_name} {p.last_name}" if p else None


def patient_ref(p: Patient) -> dict[str, Any]:
    return {"id": str(p.id), "name": patient_name(p), "reference": p.patient_reference}


def iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def serialize_journey(j: Journey, patient: Patient | None, pathway_name: str | None = None) -> dict[str, Any]:
    return {
        "id": str(j.id),
        "patient_id": str(j.patient_id),
        "status": (j.status or "").lower(),
        "priority": (j.priority or "").lower(),
        "started_at": iso(j.started_at),
        "pathway_version": j.pathway_version,
        "patient_name": patient_name(patient),
        "patient_reference": patient.patient_reference if patient else None,
        "pathway_name": pathway_name,
    }


def pathway_name_map(db: Session, pathway_ids: set[UUID]) -> dict[UUID, str]:
    if not pathway_ids:
        return {}
    return {p.id: p.name for p in db.query(Pathway).filter(Pathway.id.in_(pathway_ids)).all()}


def serialize_step(step: JourneyStep, template: PathwayStep | None) -> dict[str, Any]:
    return {
        "id": str(step.id),
        "name": template.name if template else None,
        "sequence_number": template.sequence_number if template else None,
        "status": (step.status or "").lower(),
        "owner_role": step.owner_role,
        "due_at": iso(step.due_at),
        "completed_at": iso(step.completed_at),
        "time_limit_hours": step.time_limit_hours,
        "block_reason": step.block_reason,
    }
