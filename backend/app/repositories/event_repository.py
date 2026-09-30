from uuid import UUID
from sqlalchemy.orm import Session
from app.models import PatientEvent

class EventRepository:
    def __init__(self, db: Session): self.db = db
    def get_by_external_id(self, external_event_id: str):
        return self.db.query(PatientEvent).filter(PatientEvent.external_event_id == external_event_id).first()
    def recent(self, journey_id: UUID, limit: int = 12):
        return self.db.query(PatientEvent).filter(PatientEvent.journey_id == journey_id).order_by(PatientEvent.event_time.desc()).limit(limit).all()
