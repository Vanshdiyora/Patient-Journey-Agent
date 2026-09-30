from uuid import UUID
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.authorization import require_staff
from app.models import ExceptionRecord, Journey
from app.schemas import ExceptionResponse, ExceptionUpdate

router = APIRouter()


@router.get("/exceptions", response_model=list[ExceptionResponse])
def exceptions(
    status: str | None = None,
    severity: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    user=Depends(require_staff),
):
    q = (
        db.query(ExceptionRecord)
        .join(Journey, Journey.id == ExceptionRecord.journey_id)
    )
    from app.core.authorization import scope_patient_ids
    patient_ids = scope_patient_ids(db, user)
    if patient_ids is not None:
        q = q.filter(Journey.patient_id.in_(patient_ids))
    if status:
        q = q.filter(ExceptionRecord.status == status)
    if severity:
        q = q.filter(ExceptionRecord.severity == severity)
    return q.order_by(ExceptionRecord.created_at.desc()).limit(limit).all()


@router.patch("/exceptions/{exception_id}", response_model=ExceptionResponse)
def update_exception(
    exception_id: UUID,
    data: ExceptionUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_staff),
):
    item = db.query(ExceptionRecord).filter(ExceptionRecord.id == exception_id).first()
    if not item:
        raise HTTPException(404, "Exception not found")
    # Scope check: the exception's journey must be visible to this user.
    journey = db.query(Journey).filter(Journey.id == item.journey_id).first()
    from app.core.authorization import can_read_journey
    if not journey or not can_read_journey(user, journey):
        raise HTTPException(404, "Exception not found")

    item.status = data.status
    item.recommended_action = data.recommended_action
    if data.status in {"RESOLVED", "DISMISSED"}:
        item.resolved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(item)
    return item
