from uuid import UUID
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.authorization import require_staff
from app.models import ExceptionRecord, Journey
from app.schemas import ExceptionResponse, ExceptionUpdate

router = APIRouter()

VALID_STATUSES = ("OPEN", "IN_PROGRESS", "RESOLVED", "DISMISSED")
VALID_SEVERITIES = ("CRITICAL", "HIGH", "MEDIUM", "LOW")


def _normalize(value: str | None, valid: tuple[str, ...], field: str) -> str:
    """Accept any case (UI sends lowercase; the DB enum is uppercase)."""
    if not value:
        raise HTTPException(422, f"{field} is required")
    v = value.strip().upper()
    if v not in valid:
        raise HTTPException(422, f"{field} must be one of: {', '.join(valid)}")
    return v


@router.get("/exceptions")
def exceptions(
    status: str | None = None,
    severity: str | None = None,
    limit: int = Query(10, ge=1, le=10),
    offset: int = Query(0, ge=0),
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
        # Case-insensitive, comma-separated: "open,in_progress" works too.
        wanted = [s.strip().upper() for s in status.split(",") if s.strip()]
        unknown = [s for s in wanted if s not in VALID_STATUSES]
        if unknown:
            raise HTTPException(422, f"Unknown status: {', '.join(unknown)}")
        q = q.filter(ExceptionRecord.status.in_(wanted))
    if severity:
        wanted = [s.strip().upper() for s in severity.split(",") if s.strip()]
        unknown = [s for s in wanted if s not in VALID_SEVERITIES]
        if unknown:
            raise HTTPException(422, f"Unknown severity: {', '.join(unknown)}")
        q = q.filter(ExceptionRecord.severity.in_(wanted))
    items = q.order_by(ExceptionRecord.created_at.desc(), ExceptionRecord.id.desc()).offset(offset).limit(limit).all()
    return {"items": [ExceptionResponse.model_validate(item).model_dump(mode="json") for item in items],
            "total": q.order_by(None).count(), "limit": limit, "offset": offset}


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

    # The DB enum is uppercase; the UI sends lowercase. Normalize server-side so
    # resolves work regardless of the caller's case.
    item.status = _normalize(data.status, VALID_STATUSES, "status")
    item.recommended_action = data.recommended_action
    if item.status in {"RESOLVED", "DISMISSED"}:
        item.resolved_at = datetime.now(timezone.utc)
    else:
        item.resolved_at = None
    db.commit()
    db.refresh(item)
    return item
