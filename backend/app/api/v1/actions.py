from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.authorization import require_staff, get_journey_scoped
from app.action_registry.registry import ActionRegistry
from app.models import ActionExecution
from app.orchestration.action_executor import ActionExecutor

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


class RejectBody(BaseModel):
    note: str | None = Field(default=None, max_length=500)


def _serialize(a: ActionExecution) -> dict:
    return {
        "id": str(a.id), "journey_id": str(a.journey_id), "action_type": a.action_type,
        "status": a.status, "response_payload": a.response_payload, "error_message": a.error_message,
        "completed_at": a.completed_at,
    }


def _pending_action(db: Session, action_id: UUID, user) -> ActionExecution:
    action = db.query(ActionExecution).filter(ActionExecution.id == action_id).with_for_update().first()
    if not action:
        raise HTTPException(404, "Action not found")
    get_journey_scoped(action.journey_id, db, user)  # 404 when outside the user's scope
    if action.status != "REQUESTED":
        raise HTTPException(409, f"This action is already {action.status.lower()}.")
    return action


@router.post("/actions/{action_id}/approve")
def approve_action(action_id: UUID, db: Session = Depends(get_db), user=Depends(require_staff)):
    """Staff approval: runs an action the agents were not allowed to run on their own."""
    action = _pending_action(db, action_id, user)
    ActionExecutor(db).approve(action, user)
    db.commit()
    return _serialize(action)


@router.post("/actions/{action_id}/reject")
def reject_action(action_id: UUID, body: RejectBody | None = None, db: Session = Depends(get_db), user=Depends(require_staff)):
    action = _pending_action(db, action_id, user)
    ActionExecutor(db).reject(action, user, body.note if body else None)
    db.commit()
    return _serialize(action)
