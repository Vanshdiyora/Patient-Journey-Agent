from datetime import datetime, timezone
from uuid import uuid4

class AuditService:
    def __init__(self): self.events = []
    def record(self, journey_id, category, action, details):
        self.events.append({"id": str(uuid4()), "journey_id": str(journey_id), "category": category, "action": action, "details": details, "timestamp": datetime.now(timezone.utc).isoformat()})
        return self.events[-1]
