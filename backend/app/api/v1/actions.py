from uuid import UUID
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.authorization import require_staff, get_journey_scoped
from app.action_registry.registry import ActionRegistry
from app.models import ActionExecution

router = APIRouter()


@router.get("/actions/registry")
def registry(user=Depends(require_staff)):
    return {"actions": ActionRegistry().list()}


@router.get("/journeys/{journey_id}/actions")
def actions(journey_id: UUID, db: Session = Depends(get_db), user=Depends(require_staff)):
    get_journey_scoped(journey_id, db, user)
    return (
        db.query(ActionExecution)
        .filter(ActionExecution.journey_id == journey_id)
        .order_by(ActionExecution.requested_at.desc())
        .limit(100)
        .all()
    )
