"""
Role-based access control service.

Centralizes every authorization decision:
- STAFF_ROLES see data according to assignment scope (patient-level assignment
  via users.patient_id; no assignment table exists yet, so staff scope is
  "all records" — see scope_patient_ids / scope_note).
- PATIENT role users are bound to exactly one patient via users.patient_id and
  may only ever touch their own records.
- Identity, role and patient link ALWAYS come from the authenticated DB user,
  never from request bodies.

Denials use 404 for read paths (do not leak record existence) and 403 for
action paths the role can never perform.
"""
from uuid import UUID

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.journey import Journey

STAFF_ROLES = ("ADMIN", "CLINICIAN", "CARE_COORDINATOR")
READ_ALL_ROLES = ("ADMIN",)


def require_staff(user=Depends(get_current_user)) -> User:
    """Deny patients from staff-only surfaces (403)."""
    if user.role not in STAFF_ROLES:
        raise HTTPException(403, "Staff role required")
    return user


def require_admin(user=Depends(get_current_user)) -> User:
    if user.role != "ADMIN":
        raise HTTPException(403, "Administrator role required")
    return user


def require_patient(user=Depends(get_current_user)) -> User:
    """Resolve the authenticated patient identity, with its bound patient row."""
    if user.role != "PATIENT":
        raise HTTPException(403, "Patient role required")
    if not user.patient_id:
        raise HTTPException(403, "Patient identity is not linked to a patient record")
    return user


def _deny_read() -> HTTPException:
    # Consistent 404 so callers cannot probe which journeys/patients exist.
    return HTTPException(404, "Resource not found")


def can_read_journey(user: User, journey: Journey) -> bool:
    if user.role == "ADMIN":
        return True
    if user.role == "PATIENT":
        return journey.patient_id == user.patient_id
    # Staff: assignment data is not modeled yet, so staff scope is global.
    return user.role in STAFF_ROLES


def scope_patient_ids(db: Session, user: User) -> list[UUID] | None:
    """
    Patient IDs the user may see, or None for "unrestricted" (admin, and staff
    while no finer assignment model exists).
    """
    if user.role == "ADMIN":
        return None
    if user.role == "PATIENT":
        return [user.patient_id] if user.patient_id else []
    if user.role in STAFF_ROLES:
        # TODO(assignment model): constrain to the user's team/clinic once
        # assignments exist. Until then staff scope is unrestricted.
        return None
    return []


def scope_note(user: User) -> str:
    if user.role == "ADMIN":
        return "all"
    if user.role == "PATIENT":
        return "own"
    return "assigned (global while assignments are not modeled)"


def get_journey_scoped(journey_id: UUID, db: Session, user: User) -> Journey:
    """Fetch a journey the user may READ; 404 otherwise. For reads."""
    journey = db.query(Journey).filter(Journey.id == journey_id).first()
    if not journey or not can_read_journey(user, journey):
        raise _deny_read()
    return journey


def get_journey_for_action(
    journey_id: UUID,
    db: Session,
    user: User,
    *,
    allowed_roles: tuple[str, ...] = STAFF_ROLES,
) -> Journey:
    """
    Fetch a journey the user may ACT on (evaluate/orchestrate/events). Roles
    outside allowed_roles are denied with 403; in-scope-but-unauthorized with
    404 to avoid confirming the journey exists.
    """
    if user.role not in allowed_roles:
        raise HTTPException(403, "Your role cannot perform this action")
    journey = db.query(Journey).filter(Journey.id == journey_id).first()
    if not journey or not can_read_journey(user, journey):
        raise _deny_read()
    return journey


def get_owned_patient(user: User) -> UUID:
    """Patient id bound to the authenticated patient user (403 if unlinked)."""
    if user.role != "PATIENT" or not user.patient_id:
        raise HTTPException(403, "Patient role required")
    return user.patient_id
