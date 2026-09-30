from uuid import UUID
from sqlalchemy.orm import Session
from app.agents.coordination.schemas import CoordinationDecision
from app.agents.coordination.prompts import SYSTEM_PROMPT
from app.agents.coordination.tools import allowed_actions
from app.llm.provider import get_llm_client
from app.action_registry.validators import validate_agent_action

class CoordinationAgent:
    name = "CoordinationAgent"
    run_type = "COORDINATION"

    def __init__(self, db: Session): self.db = db

    def choose_action(self, journey_id: UUID, step_context: dict):
        allowed = allowed_actions(step_context.get("step_type", ""), step_context.get("step_code", ""), step_context.get("blocked", False))
        if not allowed:
            raise ValueError("No permitted actions are configured for this step")
        llm = get_llm_client()
        if not llm: raise RuntimeError("MAQ AI is disabled")
        prompt = {
            "journey_id": str(journey_id),
            "step": step_context,
            "allowed_actions": allowed,
            "instruction": "Choose exactly one allowed action. Return JSON only."
        }
        result = llm.chat_json([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": str(prompt)},
        ])
        decision = CoordinationDecision.model_validate(result)
        validate_agent_action(decision.model_dump(), allowed)
        return decision
