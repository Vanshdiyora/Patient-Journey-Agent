from uuid import UUID
from sqlalchemy.orm import Session
from app.models import Journey, JourneyStep

class JourneyRepository:
    def __init__(self, db: Session): self.db = db
    def get(self, journey_id: UUID): return self.db.query(Journey).filter(Journey.id == journey_id).first()
    def steps(self, journey_id: UUID): return self.db.query(JourneyStep).filter(JourneyStep.journey_id == journey_id).order_by(JourneyStep.due_at.asc()).all()
    def step(self, step_id: UUID): return self.db.query(JourneyStep).filter(JourneyStep.id == step_id).first()
