"""
Admin-only user management endpoints. Every route requires the ADMIN role —
checked server-side via require_admin; the hidden UI menu is not the gate.
"""
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import normalize_account_email
from app.core.authorization import require_admin
from app.core.database import get_db
from app.core.passwords import hash_password
from app.models.patient import Patient
from app.models.staff_patient_assignment import StaffPatientAssignment
from app.models.user import User

router = APIRouter(prefix="/admin", tags=["admin"])

VALID_ROLES = ("ADMIN", "CLINICIAN", "CARE_COORDINATOR", "PATIENT")


def _audit_change(db: Session, admin: User, action: str, parameters: dict) -> None:
    from app.services.chat_service import audit

    audit(db, user=admin, tool_name=action, event="executed",
          parameters=parameters, correlation_id=uuid.uuid4(), result_status="success")


class RoleUpdate(BaseModel):
    role: str


class StatusUpdate(BaseModel):
    is_active: bool


class StaffCreate(BaseModel):
    email: str
    display_name: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=8, max_length=128)
    role: str

    @field_validator("email", mode="before")
    @classmethod
    def validate_email(cls, value):
        return normalize_account_email(value)


def _serialize(u: User) -> dict:
    return {
        "id": str(u.id),
        "email": u.email,
        "display_name": u.display_name,
        "role": u.role,
        "patient_id": str(u.patient_id) if u.patient_id else None,
        "is_active": u.is_active,
        "created_at": u.created_at,
        "updated_at": u.updated_at,
    }


@router.get("/users")
def list_users(
    role: str | None = None,
    search: str | None = None,
    limit: int = Query(10, ge=1, le=10),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    q = db.query(User)
    if role:
        if role not in VALID_ROLES:
            raise HTTPException(422, "Unknown role")
        q = q.filter(User.role == role)
    if search:
        term = f"%{search}%"
        q = q.filter(User.email.ilike(term) | User.display_name.ilike(term))
    total = q.order_by(None).count()
    items = q.order_by(User.created_at.desc(), User.id.desc()).offset(offset).limit(limit).all()
    return {"items": [_serialize(u) for u in items], "total": total, "limit": limit, "offset": offset}


@router.post("/users", status_code=201)
def create_staff_user(
    data: StaffCreate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Only an administrator may provision a privileged account."""
    if data.role not in ("ADMIN", "CLINICIAN", "CARE_COORDINATOR"):
        raise HTTPException(422, "Choose an administrator or staff role")
    now = datetime.now(timezone.utc)
    user = User(id=uuid.uuid4(), email=data.email, display_name=data.display_name.strip(),
                password_hash=hash_password(data.password), role=data.role, patient_id=None,
                is_active=True, created_at=now, updated_at=now)
    db.add(user)
    _audit_change(db, _admin, "create_staff_user", {"user_id": str(user.id), "role": user.role})
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "An account with this email already exists") from exc
    db.refresh(user)
    return _serialize(user)


def _assignable_staff(db: Session, user_id: uuid.UUID) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user or user.role not in ("CLINICIAN", "CARE_COORDINATOR"):
        raise HTTPException(404, "Clinical or coordination staff user not found")
    return user


@router.get("/users/{user_id}/patients")
def list_patient_assignments(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    _assignable_staff(db, user_id)
    rows = db.query(StaffPatientAssignment, Patient).join(
        Patient, Patient.id == StaffPatientAssignment.patient_id
    ).filter(
        StaffPatientAssignment.staff_user_id == user_id
    ).order_by(StaffPatientAssignment.created_at, StaffPatientAssignment.id).all()
    return {
        "patient_ids": [str(assignment.patient_id) for assignment, _ in rows],
        "patients": [{"id": str(patient.id), "name": f"{patient.first_name} {patient.last_name}",
                      "reference": patient.patient_reference} for _, patient in rows],
    }


@router.put("/users/{user_id}/patients/{patient_id}")
def assign_patient(
    user_id: uuid.UUID,
    patient_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    _assignable_staff(db, user_id)
    if not db.query(Patient.id).filter(Patient.id == patient_id).first():
        raise HTTPException(404, "Patient not found")
    existing = db.query(StaffPatientAssignment).filter(
        StaffPatientAssignment.staff_user_id == user_id,
        StaffPatientAssignment.patient_id == patient_id,
    ).first()
    if not existing:
        db.add(StaffPatientAssignment(staff_user_id=user_id, patient_id=patient_id,
                                      assigned_by_user_id=admin.id))
        _audit_change(db, admin, "assign_patient", {"user_id": str(user_id), "patient_id": str(patient_id)})
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            already_granted = db.query(StaffPatientAssignment.id).filter(
                StaffPatientAssignment.staff_user_id == user_id,
                StaffPatientAssignment.patient_id == patient_id,
            ).first()
            if not already_granted:
                raise HTTPException(500, "Could not grant patient access") from exc
    return {"staff_user_id": str(user_id), "patient_id": str(patient_id), "assigned": True}


@router.delete("/users/{user_id}/patients/{patient_id}")
def unassign_patient(
    user_id: uuid.UUID,
    patient_id: uuid.UUID,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    _assignable_staff(db, user_id)
    row = db.query(StaffPatientAssignment).filter(
        StaffPatientAssignment.staff_user_id == user_id,
        StaffPatientAssignment.patient_id == patient_id,
    ).first()
    if row:
        db.delete(row)
        _audit_change(db, _admin, "unassign_patient", {"user_id": str(user_id), "patient_id": str(patient_id)})
        db.commit()
    return {"staff_user_id": str(user_id), "patient_id": str(patient_id), "assigned": False}


@router.patch("/users/{user_id}/role")
def set_user_role(
    user_id: uuid.UUID,
    data: RoleUpdate,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    if data.role not in VALID_ROLES:
        raise HTTPException(422, f"Role must be one of: {', '.join(VALID_ROLES)}")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    if data.role == "PATIENT" and not user.patient_id:
        raise HTTPException(422, "Cannot assign the PATIENT role without linking a patient record")
    if user.role == "PATIENT" and data.role != "PATIENT":
        raise HTTPException(422, "Patient accounts cannot be converted to staff accounts")
    user.role = data.role
    user.updated_at = datetime.now(timezone.utc)
    _audit_change(db, _admin, "set_user_role", {"user_id": str(user_id), "role": data.role})
    db.commit()
    db.refresh(user)
    return _serialize(user)


@router.patch("/users/{user_id}/status")
def set_user_status(
    user_id: uuid.UUID,
    data: StatusUpdate,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    user.is_active = data.is_active
    user.updated_at = datetime.now(timezone.utc)
    _audit_change(db, _admin, "set_user_status", {"user_id": str(user_id), "is_active": data.is_active})
    db.commit()
    db.refresh(user)
    return _serialize(user)
