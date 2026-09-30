from uuid import UUID
from sqlalchemy.orm import Session
from app.agents.journey_intelligence.schemas import JourneyAssessment
from app.agents.journey_intelligence.prompts import SYSTEM_PROMPT
from app.agents.journey_intelligence.tools import build_context
from app.llm.provider import get_llm_client

class JourneyIntelligenceAgent:
    name = "JourneyIntelligenceAgent"
    run_type = "JOURNEY_INTELLIGENCE"

    def __init__(self, db: Session): self.db = db

    def assess(self, journey_id: UUID):
        context = build_context(self.db, journey_id)
        if not context: raise ValueError("Journey not found")
        llm = get_llm_client()
        if not llm: raise RuntimeError("MAQ AI is disabled")
        result = llm.chat_json([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Journey context: {context}"},
        ])
        return JourneyAssessment.model_validate(result), context
