import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models import PatientEvent, Journey
from app.orchestration.journey_engine import JourneyEngine

class EventProcessor:
    def __init__(self, db: Session): self.db = db

    def ingest(self, journey_id, event_type, source, event_time, payload, external_event_id=None):
        journey = self.db.query(Journey).filter(Journey.id == journey_id).first()
        if not journey: raise ValueError("Journey not found")
        if external_event_id:
            existing = self.db.query(PatientEvent).filter(PatientEvent.external_event_id == external_event_id).first()
            if existing: return existing, {"duplicate": True, "orchestration": None}
        event = PatientEvent(
            id=uuid.uuid4(), patient_id=journey.patient_id, journey_id=journey.id,
            event_type=event_type, source=source, external_event_id=external_event_id,
            event_time=event_time, payload=payload or {}, processed=False,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(event); self.db.flush()
        result = JourneyEngine(self.db).process_event(journey.id, event)
        event.processed = True
        self.db.commit(); self.db.refresh(event)
        return event, result
