from sqlalchemy.orm import Session
from app.models import AgentRun

class AgentRepository:
    def __init__(self, db: Session): self.db = db
    def save(self, run: AgentRun): self.db.add(run); self.db.flush(); return run
