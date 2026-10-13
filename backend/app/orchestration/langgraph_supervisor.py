"""
Orchestration graph (LangGraph).

    START -> deterministic -> supervisor -> journey_intelligence -> supervisor
                                         -> coordination -> execute -> deterministic -> supervisor
                                         -> wait | escalate -> END

* `deterministic` runs the rule engine (dependencies, deadlines) and refreshes
  the context. It runs again after every executed action so the supervisor
  never decides on stale state.
* `supervisor` / `journey_intelligence` / `coordination` use the LLM. Their
  output is sanitized by RulesPolicy; if the AI is unavailable or unusable the
  run continues on the rules alone (mode RULES_ONLY) instead of failing.
* Agents can only ever choose from the Action Registry. An agent-owned step is
  completed only by a verified action that fulfils it (see
  _complete_agent_owned_step). Every other status change comes from the rules
  or from staff/patients.
"""
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from app.action_registry.registry import ActionRegistry
from app.agents.coordination.agent import CoordinationAgent
from app.agents.journey_intelligence.agent import JourneyIntelligenceAgent
from app.agents.supervisor.agent import SupervisorAgent
from app.agents.supervisor.state import SupervisorState
from app.agents.supervisor.tools import build_supervisor_context
from app.audit.trace import record_agent_run
from app.core.config import settings
from app.models import ExceptionRecord, Journey, JourneyStep, PathwayStep, PatientEvent
from app.orchestration.action_executor import ActionExecutor
from app.orchestration.journey_engine import JourneyEngine
from app.orchestration.policy import RulesPolicy, llm_failure_reason
from app.orchestration.run_report import build_summary, snapshot, step_changes


class OrchestrationFailure(Exception):
    """Unexpected failure of a run; the message is safe to show to staff."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


class SupervisorGraph:
    def __init__(self, db: Session):
        self.db = db
        self.policy = RulesPolicy(db)
        self.registry = ActionRegistry()
        self.graph = self._build()

    # ------------------------------------------------------------------ graph
    def _build(self):
        builder = StateGraph(SupervisorState)
        builder.add_node("deterministic", self._deterministic)
        builder.add_node("supervisor", self._supervisor)
        builder.add_node("journey_intelligence", self._journey_intelligence)
        builder.add_node("coordination", self._coordination)
        builder.add_node("execute", self._execute)
        builder.add_node("wait", self._wait)
        builder.add_node("escalate", self._escalate)
        builder.add_edge(START, "deterministic")
        builder.add_edge("deterministic", "supervisor")
        builder.add_conditional_edges("supervisor", self._route, {
            "journey_intelligence": "journey_intelligence",
            "coordination": "coordination",
            "wait": "wait",
            "escalate": "escalate",
        })
        builder.add_edge("journey_intelligence", "supervisor")
        builder.add_conditional_edges("coordination", self._after_coordination, {"execute": "execute", "wait": "wait"})
        builder.add_edge("execute", "deterministic")
        builder.add_edge("wait", END)
        builder.add_edge("escalate", END)
        return builder.compile()

    def _route(self, state: SupervisorState):
        return {
            "JOURNEY_INTELLIGENCE": "journey_intelligence",
            "COORDINATION": "coordination",
            "ESCALATE": "escalate",
        }.get(state.get("decision", {}).get("next_capability"), "wait")

    @staticmethod
    def _after_coordination(state: SupervisorState):
        return "execute" if state.get("decision", {}).get("action_type") else "wait"

    # --------------------------------------------------------------- helpers
    def _log(self, state, entry: dict[str, Any]):
        state["calls"] = state.get("calls", []) + [entry]

    def _degrade(self, state, component: str, exc: Exception, journey_id: UUID, context: dict | None = None):
        """AI failed: record it, switch the rest of the run to rules-only."""
        reason = llm_failure_reason(exc)
        state["mode"] = "RULES_ONLY"
        state["warnings"] = state.get("warnings", []) + [f"{component}: {reason}"]
        self._log(state, {"component": component, "operation": "ai_unavailable", "reason": reason})
        record_agent_run(
            self.db, journey_id, component.replace(" ", ""), component.upper().replace(" ", "_"),
            context or {}, None, [], "FAILED", error_message=f"Fell back to rules: {reason}.",
        )

    def _open_exception(self, journey_id: UUID, step_id: str | None, exc_type: str, title: str,
                        description: str, severity: str, recommended: str):
        """Surface something for staff on the Exceptions page (deduplicated)."""
        sid = UUID(step_id) if step_id else None
        existing = self.db.query(ExceptionRecord).filter(
            ExceptionRecord.journey_id == journey_id,
            ExceptionRecord.journey_step_id == sid,
            ExceptionRecord.exception_type == exc_type,
            ExceptionRecord.status.in_(("OPEN", "IN_PROGRESS")),
        ).first()
        if existing:
            return existing, False
        item = ExceptionRecord(
            id=uuid4(), journey_id=journey_id, journey_step_id=sid, severity=severity,
            exception_type=exc_type, title=title, description=description, status="OPEN",
            recommended_action=recommended, created_at=_now(), resolved_at=None,
        )
        self.db.add(item)
        self.db.flush()
        return item, True

    def _severity(self, journey_id: UUID) -> str:
        journey = self.db.query(Journey).filter(Journey.id == journey_id).first()
        return journey.priority if journey and journey.priority in ("CRITICAL", "HIGH") else "MEDIUM"

    # ----------------------------------------------------------------- nodes
    def _deterministic(self, state: SupervisorState):
        journey_id = UUID(state["journey_id"])
        context = build_supervisor_context(self.db, journey_id)
        state["context"] = context or {}
        self._log(state, {"component": "deterministic_control_plane", "operation": "evaluate_journey"})
        return state

    def _supervisor(self, state: SupervisorState):
        journey_id = UUID(state["journey_id"])
        state["iteration"] = state.get("iteration", 0) + 1
        if state["iteration"] > settings.supervisor_max_iterations:
            state["decision"] = {"next_capability": "WAIT", "reason": "Maximum supervisor iterations reached", "source": "rules"}
            self._log(state, {"component": "supervisor", "decision": state["decision"]})
            return state

        decision = None
        source = "supervisor"
        if state.get("mode") != "RULES_ONLY":
            agent = SupervisorAgent(self.db)
            source = agent.name
            context = {
                **state.get("context", {}),
                "already_handled_step_ids": state.get("attempted", []),
                "journey_assessment_done": bool(state.get("ji_done")),
            }
            try:
                raw = agent.decide(journey_id, context)
                decision = self.policy.sanitize_supervisor(raw, state)
                record_agent_run(self.db, journey_id, agent.name, agent.run_type, context, decision, [], "SUCCESS")
            except Exception as exc:  # noqa: BLE001 - any AI failure degrades to rules
                self._degrade(state, "Supervisor Agent", exc, journey_id, context)
        if decision is None:
            decision = self.policy.supervisor_decision(state)
        state["decision"] = decision
        self._log(state, {"component": "supervisor" if decision.get("source") == "rules" else source, "decision": decision})
        return state

    def _journey_intelligence(self, state: SupervisorState):
        journey_id = UUID(state["journey_id"])
        state["ji_done"] = True
        agent = JourneyIntelligenceAgent(self.db)
        try:
            assessment, context = agent.assess(journey_id)
        except Exception as exc:  # noqa: BLE001
            self._degrade(state, "Journey Intelligence Agent", exc, journey_id)
            return state
        output = assessment.model_dump()
        state["result"] = {"journey_intelligence": output}
        state["outcomes"] = state.get("outcomes", []) + [{"component": agent.name, "output": output}]
        state["context"] = {**state.get("context", {}), "journey_intelligence": output}
        self._log(state, {"component": agent.name, "output": output})
        record_agent_run(self.db, journey_id, agent.name, agent.run_type, context, output, [], "SUCCESS")
        return state

    def _coordination(self, state: SupervisorState):
        journey_id = UUID(state["journey_id"])
        decision = dict(state.get("decision", {}))
        step = self.policy.step_by_id(state, decision.get("target_step_id")) or self.policy.next_actionable(state)
        if not step:
            state["decision"] = self.policy._wait("No actionable step found.")
            self._log(state, {"component": "coordination", "outcome": "WAIT", "reason": state["decision"]["reason"]})
            return state

        decision.update(self.policy._target(step))
        state["attempted"] = state.get("attempted", []) + [step["journey_step_id"]]
        action_type = payload = reason = None

        if state.get("mode") != "RULES_ONLY":
            agent = CoordinationAgent(self.db)
            try:
                coord = agent.choose_action(journey_id, {
                    "journey_step_id": step["journey_step_id"], "step_code": step.get("step_code"),
                    "step_type": step.get("step_type"), "blocked": step.get("blocked"),
                    "reason": step.get("reason"), "supervisor_context": state.get("context"),
                })
                action_type, payload, reason = coord.action_type, coord.payload or {}, coord.reason
                output = coord.model_dump()
                state["result"] = {"coordination": output}
                state["outcomes"] = state.get("outcomes", []) + [{"component": agent.name, "output": output}]
                self._log(state, {"component": agent.name, "output": output})
                record_agent_run(self.db, journey_id, agent.name, agent.run_type, state.get("context", {}), output, [], "SUCCESS")
            except Exception as exc:  # noqa: BLE001
                self._degrade(state, "Coordination Agent", exc, journey_id, {"step": step})
        if action_type is None:
            picked = self.policy.coordination_action(step)
            if picked is None:
                state["decision"] = self.policy._wait("No permitted action is configured for this step.")
                self._log(state, {"component": "coordination", "outcome": "WAIT", "reason": state["decision"]["reason"]})
                return state
            (action_type, reason), payload = picked, {}

        base = {
            "journey_id": state["journey_id"], "patient_id": (state.get("context", {}).get("journey") or {}).get("patient_id"),
            "step_code": step.get("step_code"), "step_name": step.get("step_name"), "reason": step.get("reason"),
        }
        decision.update({
            "action_type": action_type, "action_reason": reason,
            "payload": {**{k: v for k, v in base.items() if v is not None}, **(payload or {})},
        })
        state["decision"] = decision
        return state

    def _execute(self, state: SupervisorState):
        journey_id = UUID(state["journey_id"])
        decision = state["decision"]
        step_id = decision.get("target_step_id")
        execution, meta = ActionExecutor(self.db).execute(
            journey_id, UUID(step_id) if step_id else None, decision["action_type"],
            decision.get("payload") or {}, requested_by="SUPERVISOR",
            allow_agent_self_approval=True,
        )
        completed, note = self._complete_agent_owned_step(journey_id, step_id, execution, meta)
        if completed:
            state["agent_completed"] = state.get("agent_completed", []) + [step_id]
        if execution.status == "FAILED":
            state["failed_steps"] = state.get("failed_steps", []) + [step_id]
        if meta.get("awaiting_approval"):
            item, created = self._open_exception(
                journey_id, step_id, "ACTION_AWAITING_APPROVAL",
                f"Approval needed: {decision['action_type'].replace('_', ' ').title()}",
                f"The agent proposed '{decision['action_type']}' for '{decision.get('target_step_name')}', "
                "but this action needs staff approval before it can run.",
                self._severity(journey_id), "Review the step and carry out the follow-up manually.",
            )
        output = {
            "id": str(execution.id), "status": execution.status, "action_type": execution.action_type,
            "response": execution.response_payload, "error": execution.error_message,
            "step_id": step_id, "step_name": decision.get("target_step_name"),
            "reason": decision.get("action_reason"), "step_completed": completed, "step_completion_note": note,
            **meta,
        }
        state["result"] = {"action_execution": output}
        state["outcomes"] = state.get("outcomes", []) + [{"component": "action_executor", "output": output}]
        self._log(state, {"component": "action_executor", "output": output})
        return state

    def _complete_agent_owned_step(self, journey_id, step_id, execution, meta) -> tuple[bool, str]:
        """
        The ONLY place an agent changes a step's status. All must hold:
          1. the action executed successfully and was verified (not approval-gated, not failed)
          2. the step belongs to this journey and its owner is AGENT
          3. the step is READY or IN_PROGRESS
          4. the action actually fulfils that kind of step (registry rule)
        """
        if not step_id:
            return False, "No step was targeted."
        if meta.get("awaiting_approval"):
            return False, "The action is waiting for staff approval, so the step was not completed."
        if execution.status != "SUCCESS" or meta.get("verified") is not True:
            return False, "The action did not complete and verify, so the step was not completed."
        row = (
            self.db.query(JourneyStep, PathwayStep)
            .join(PathwayStep, JourneyStep.pathway_step_id == PathwayStep.id)
            .filter(JourneyStep.id == UUID(str(step_id)), JourneyStep.journey_id == journey_id)
            .with_for_update().first()
        )
        journey = self.db.query(Journey).filter(Journey.id == journey_id).first()
        if not row or not journey:
            return False, "The step was not found on this journey."
        step, template = row
        owner = step.owner_role or template.owner_role or "CLINICIAN"
        if owner != "AGENT":
            return False, f"This step is owned by {owner.replace('_', ' ').lower()}, so only they can complete it; the action was sent as support."
        if step.status not in {"READY", "IN_PROGRESS"}:
            return False, f"The step is {step.status.lower()}, not ready, so it cannot be completed yet."
        if not self.registry.fulfils_step(execution.action_type, template.step_type, template.code):
            return False, f"{execution.action_type.replace('_', ' ').title()} does not fulfil a {template.step_type.lower()} step, so it was not completed."

        now = _now()
        step.status = "COMPLETED"
        step.completed_at = now
        step.block_reason = None
        step.updated_at = now
        self.db.add(PatientEvent(
            id=uuid4(), patient_id=journey.patient_id, journey_id=journey_id,
            event_type="STEP_COMPLETED", source="verified-agent-action", external_event_id=None,
            event_time=now,
            payload={
                "journey_step_id": str(step.id), "step_code": template.code, "owner_role": "AGENT",
                "step_completed": True, "verified": True, "action_execution_id": str(execution.id),
                "action_type": execution.action_type,
                "confirmation": "The assigned agent action completed successfully and passed verification.",
            },
            processed=True, created_at=now,
        ))
        JourneyEngine(self.db).evaluate(journey_id)
        return True, "Completed: the verified action fulfils this agent-owned step."

    def _wait(self, state: SupervisorState):
        state["status"] = "WAIT"
        self._log(state, {"component": "supervisor", "outcome": "WAIT", "reason": state.get("decision", {}).get("reason")})
        return state

    def _escalate(self, state: SupervisorState):
        journey_id = UUID(state["journey_id"])
        decision = state.get("decision", {})
        step_id = decision.get("target_step_id")
        if not step_id:
            step = next((s for s in self.policy.steps(state) if s.get("blocked")), None)
            step_id = step["journey_step_id"] if step else None
            if step:
                decision.update(self.policy._target(step))
        item, created = self._open_exception(
            journey_id, step_id, "AGENT_ESCALATION", "Escalated by the orchestration agents",
            decision.get("reason") or "The agents could not resolve this journey on their own.",
            self._severity(journey_id), "Review the journey and contact the patient or the responsible team.",
        )
        decision["escalation_exception_id"] = str(item.id)
        state["decision"] = decision
        state["status"] = "ESCALATE"
        self._log(state, {"component": "supervisor", "outcome": "ESCALATE", "reason": decision.get("reason"),
                          "exception_id": str(item.id), "exception_created": created})
        return state

    # ------------------------------------------------------------------- run
    def run(self, journey_id):
        started_at = _now()
        before = snapshot(self.db, journey_id)
        state: SupervisorState = {
            "journey_id": str(journey_id), "iteration": 0, "calls": [], "outcomes": [], "status": "RUNNING",
            "mode": "AI", "warnings": [], "attempted": [], "failed_steps": [], "agent_completed": [], "ji_done": False,
        }
        try:
            result = self.graph.invoke(state, config={"recursion_limit": settings.supervisor_max_iterations * 4 + 8})
        except Exception as exc:  # noqa: BLE001
            self.db.rollback()
            friendly = f"Orchestration could not finish ({llm_failure_reason(exc)}). No changes were saved."
            record_agent_run(
                self.db, journey_id, "Orchestration", "ORCHESTRATION", {"journey_id": str(journey_id)},
                {"summary": friendly}, [], "FAILED", error_message=friendly, started_at=started_at,
            )
            self.db.commit()
            raise OrchestrationFailure(friendly) from exc

        after = snapshot(self.db, journey_id)
        changes = step_changes(before, after, result.get("agent_completed", []))
        journey_change = (
            {"from": before["journey_status"], "to": after["journey_status"]}
            if before["journey_status"] != after["journey_status"] else None
        )
        summary = build_summary(result, changes, journey_change)
        report = {
            "summary": summary,
            "mode": result.get("mode", "AI"),
            "warnings": result.get("warnings", []),
            "step_changes": changes,
            "journey_status": {"from": before["journey_status"], "to": after["journey_status"]},
        }
        output = {
            "decision": result.get("decision"), "result": result.get("result"),
            "outcomes": result.get("outcomes", []), "final_state": result.get("status"), **report,
        }
        # agent_runs.status is a DB enum (SUCCESS | FAILED): the run itself succeeded;
        # how it ended (WAIT / ESCALATE) lives in the output as final_state.
        run = record_agent_run(
            self.db, journey_id, "Orchestration", "ORCHESTRATION", {"journey_id": str(journey_id)},
            output, result.get("calls", []), "SUCCESS", started_at=started_at,
        )
        self.db.commit()
        result.update(report)
        result["run_id"] = str(run.id)
        return result
