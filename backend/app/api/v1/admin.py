"""
Admin-only user management endpoints. Every route requires the ADMIN role —
checked server-side via require_admin; the hidden UI menu is not the gate.
"""
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.authorization import require_admin
from app.core.database import get_db
from app.models.user import User

router = APIRouter(prefix="/admin", tags=["admin"])

VALID_ROLES = ("ADMIN", "CLINICIAN", "CARE_COORDINATOR", "PATIENT")


class RoleUpdate(BaseModel):
    role: str


class StatusUpdate(BaseModel):
    is_active: bool


def _serialize(u: User) -> dict:
    return {
        "id": str(u.id),
        "email": u.email,
        "entra_object_id": u.entra_object_id,
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
    limit: int = Query(100, ge=1, le=500),
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
    items = q.order_by(User.created_at.desc()).offset(offset).limit(limit).all()
    return {"items": [_serialize(u) for u in items], "total": total, "limit": limit, "offset": offset}


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
    user.role = data.role
    user.updated_at = datetime.now(timezone.utc)
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
    db.commit()
    db.refresh(user)
    return _serialize(user)
