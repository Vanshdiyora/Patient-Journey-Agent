"""
Deterministic policy used by the orchestration graph.

It plays two roles:
  * Guard-rail: sanitizes whatever the Supervisor / Coordination LLM returns so
    a bad answer (unknown capability, hallucinated step id, repeat action) can
    never derail a run.
  * Fallback: when the AI service is unavailable or unusable, the same graph
    runs on these rules instead of failing, and the run is labelled
    RULES_ONLY so staff can see no AI was involved.
"""
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.action_registry.registry import ActionRegistry
from app.models import ExceptionRecord, Journey, JourneyStep
from app.rules.escalation_engine import EscalationEngine

CAPABILITIES = ("DETERMINISTIC", "JOURNEY_INTELLIGENCE", "COORDINATION", "WAIT", "ESCALATE")
TERMINAL = {"COMPLETED", "CANCELLED"}

ACTION_LABELS = {
    "SEND_REMINDER": "Sent a reminder",
    "REQUEST_DOCUMENT": "Requested a document",
    "REQUEST_APPOINTMENT": "Requested an appointment",
    "RESCHEDULE_APPOINTMENT": "Requested a reschedule",
    "CREATE_COORDINATOR_TASK": "Created a coordinator task",
}


def llm_failure_reason(exc: Exception) -> str:
    """Short, safe description of why the AI could not be used (never the raw error)."""
    name = type(exc).__name__
    text = str(exc)
    if "disabled" in text.lower():
        return "the AI service is disabled"
    if name == "AuthenticationError" or text.startswith("Error code: 401"):
        return "the AI service rejected the configured API key"
    if name in ("APITimeoutError", "Timeout", "ReadTimeout"):
        return "the AI service timed out"
    if name == "APIConnectionError":
        return "the AI service could not be reached"
    if name == "RateLimitError":
        return "the AI service is rate limited"
    if name in ("ValidationError", "JSONDecodeError", "ValueError", "ActionNotAllowedError"):
        return "the AI returned an answer that could not be used"
    return "the AI service is unavailable"


class RulesPolicy:
    def __init__(self, db: Session):
        self.db = db
        self.registry = ActionRegistry()

    # ---- helpers -------------------------------------------------------
    @staticmethod
    def steps(state) -> list[dict[str, Any]]:
        return (state.get("context") or {}).get("steps", [])

    def step_by_id(self, state, step_id: str | None) -> dict[str, Any] | None:
        return next((s for s in self.steps(state) if s.get("journey_step_id") == step_id), None)

    def next_actionable(self, state) -> dict[str, Any] | None:
        """First blocked step, then first agent-owned ready step, not yet handled this run."""
        handled = set(state.get("attempted", []))
        steps = [s for s in self.steps(state) if s.get("journey_step_id") not in handled]
        blocked = next((s for s in steps if s.get("blocked")), None)
        if blocked:
            return blocked
        return next((s for s in steps if s.get("ready") and s.get("owner_role") == "AGENT"), None)

    def _should_escalate(self, journey_id: str, step_id: str) -> bool:
        journey = self.db.query(Journey).filter(Journey.id == UUID(journey_id)).first()
        step = self.db.query(JourneyStep).filter(JourneyStep.id == UUID(step_id)).first()
        if not journey or not step:
            return False
        open_count = (
            self.db.query(ExceptionRecord)
            .filter(ExceptionRecord.journey_id == journey.id, ExceptionRecord.status.in_(("OPEN", "IN_PROGRESS")))
            .count()
        )
        return EscalationEngine().evaluate(journey, step, open_count)["should_escalate"]

    # ---- sanitizing the LLM supervisor ---------------------------------
    def sanitize_supervisor(self, raw: dict[str, Any], state) -> dict[str, Any]:
        capability = str(raw.get("next_capability") or "WAIT").upper()
        reason = str(raw.get("reason") or "").strip() or None
        decision: dict[str, Any] = {"next_capability": capability, "reason": reason, "source": "ai"}

        if (state.get("context") or {}).get("journey", {}).get("status") in ("CANCELLED", "COMPLETED"):
            return self._wait("The journey is closed; the agents have nothing to do.", "ai")
        if capability not in CAPABILITIES:
            return self._wait(f"The AI suggested an unknown capability ({capability}); waiting instead.", "ai")
        if capability == "JOURNEY_INTELLIGENCE" and state.get("ji_done"):
            return self._wait("The journey was already assessed in this run.", "ai")
        if capability == "COORDINATION":
            step = self.step_by_id(state, raw.get("target_step_id"))
            if step is None and raw.get("target_step_code"):
                step = next((s for s in self.steps(state) if s.get("step_code") == raw["target_step_code"]), None)
            if step is None:
                step = self.next_actionable(state)
            if step is None or step.get("journey_step_id") in state.get("attempted", []):
                return self._wait("No step is left that needs an agent action.", "ai")
            decision.update(self._target(step))
            decision["payload"] = raw.get("payload") if isinstance(raw.get("payload"), dict) else {}
        return decision

    @staticmethod
    def _target(step: dict[str, Any]) -> dict[str, Any]:
        return {
            "target_step_id": step.get("journey_step_id"),
            "target_step_code": step.get("step_code"),
            "target_step_name": step.get("step_name"),
        }

    @staticmethod
    def _wait(reason: str, source: str = "rules") -> dict[str, Any]:
        return {"next_capability": "WAIT", "reason": reason, "source": source}

    # ---- rule-based supervisor ------------------------------------------
    def supervisor_decision(self, state) -> dict[str, Any]:
        steps = self.steps(state)
        journey_id = state["journey_id"]
        journey_status = (state.get("context") or {}).get("journey", {}).get("status")
        if journey_status in ("CANCELLED", "COMPLETED"):
            return self._wait(f"The journey is {journey_status.lower()}; the agents have nothing to do.")
        if steps and all(s.get("status") in TERMINAL for s in steps):
            return self._wait("Every step is complete; nothing left for the agents to do.")

        for step_id in state.get("failed_steps", []):
            step = self.step_by_id(state, step_id) or {}
            return {
                "next_capability": "ESCALATE", "source": "rules", **self._target(step),
                "reason": f"The automated action for '{step.get('step_name', 'a step')}' failed; staff follow-up is needed.",
            }

        step = self.next_actionable(state)
        if step:
            what = "is blocked" if step.get("blocked") else "is assigned to the agent"
            return {
                "next_capability": "COORDINATION", "source": "rules", **self._target(step),
                "reason": f"'{step.get('step_name')}' {what}; choosing a permitted follow-up action.",
            }

        handled_blocked = [s for s in steps if s.get("blocked") and s.get("journey_step_id") in state.get("attempted", [])]
        for step in handled_blocked:
            if self._should_escalate(journey_id, step["journey_step_id"]):
                return {
                    "next_capability": "ESCALATE", "source": "rules", **self._target(step),
                    "reason": f"'{step.get('step_name')}' is still blocked and the escalation threshold was reached.",
                }
        if handled_blocked:
            return self._wait("Follow-up for the blocked step(s) was sent; waiting for the patient or care team to respond.")
        return self._wait("No step needs an agent action right now; the remaining steps belong to the patient or staff.")

    # ---- rule-based coordination -----------------------------------------
    def coordination_action(self, step: dict[str, Any]) -> tuple[str, str] | None:
        allowed = self.registry.allowed_for_step(step.get("step_type"), step.get("step_code"), bool(step.get("blocked")))
        allowed = [a for a in allowed if a]
        if not allowed:
            return None
        # Prefer an action that can run without human approval.
        pick = next((a for a in allowed if not a.requires_approval), allowed[0])
        return pick.action_type, f"Default permitted action for a {str(step.get('step_type') or 'general').lower()} step."
