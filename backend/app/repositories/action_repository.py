from uuid import UUID
from sqlalchemy.orm import Session
from app.models import ActionExecution

class ActionRepository:
    def __init__(self, db: Session): self.db = db
    def by_idempotency_key(self, key: str):
        return self.db.query(ActionExecution).filter(ActionExecution.idempotency_key == key).first()
    def recent_for_journey(self, journey_id: UUID, limit: int = 50):
        return self.db.query(ActionExecution).filter(ActionExecution.journey_id == journey_id).order_by(ActionExecution.requested_at.desc()).limit(limit).all()
