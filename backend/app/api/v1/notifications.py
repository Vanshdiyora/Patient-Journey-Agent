from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.authorization import can_read_journey, scope_patient_ids
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models import InAppNotification, Journey

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _scoped_notifications(db: Session, user):
    query = (
        db.query(InAppNotification)
        .join(Journey, Journey.id == InAppNotification.journey_id)
        .filter(InAppNotification.user_id == user.id)
    )
    patient_ids = scope_patient_ids(db, user)
    if patient_ids is not None:
        query = query.filter(Journey.patient_id.in_(patient_ids))
    return query


def _serialize(notification: InAppNotification) -> dict:
    return {
        "id": str(notification.id),
        "journey_id": str(notification.journey_id),
        "type": notification.notification_type,
        "title": notification.title,
        "body": notification.body,
        "created_at": notification.created_at,
        "read_at": notification.read_at,
    }


@router.get("")
def list_notifications(
    limit: int = Query(10, ge=1, le=10),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    query = _scoped_notifications(db, user)
    total = query.order_by(None).count()
    unread = query.filter(InAppNotification.read_at.is_(None)).count()
    items = (
        query.order_by(InAppNotification.created_at.desc(), InAppNotification.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return {
        "items": [_serialize(item) for item in items],
        "total": total,
        "unread": unread,
        "limit": limit,
        "offset": offset,
    }


@router.patch("/{notification_id}/read")
def mark_notification_read(
    notification_id: UUID,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    notification = (
        db.query(InAppNotification)
        .join(Journey, Journey.id == InAppNotification.journey_id)
        .filter(InAppNotification.id == notification_id, InAppNotification.user_id == user.id)
        .first()
    )
    journey = db.query(Journey).filter(Journey.id == notification.journey_id).first() if notification else None
    if not notification or not journey or not can_read_journey(db, user, journey):
        raise HTTPException(404, "Notification not found")

    if notification.read_at is None:
        notification.read_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(notification)
    return _serialize(notification)
