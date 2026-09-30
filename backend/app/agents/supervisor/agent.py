from uuid import UUID
from sqlalchemy.orm import Session
from app.agents.supervisor.prompts import SYSTEM_PROMPT
from app.agents.supervisor.tools import build_supervisor_context
from app.llm.provider import get_llm_client

class SupervisorAgent:
    name = "SupervisorAgent"
    run_type = "SUPERVISOR"

    def __init__(self, db: Session): self.db = db

    def decide(self, journey_id: UUID, context: dict | None = None):
        context = context or build_supervisor_context(self.db, journey_id)
        if not context: raise ValueError("Journey not found")
        llm = get_llm_client()
        if not llm: raise RuntimeError("MAQ AI is disabled")
        return llm.chat_json([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Current journey control-plane context: {context}"},
        ])
