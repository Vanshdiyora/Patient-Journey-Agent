from typing import Any
from datetime import datetime, timezone
from uuid import UUID, uuid4
from sqlalchemy.orm import Session
from langgraph.graph import StateGraph, START, END
from app.agents.supervisor.state import SupervisorState
from app.agents.supervisor.agent import SupervisorAgent
from app.agents.journey_intelligence.agent import JourneyIntelligenceAgent
from app.agents.coordination.agent import CoordinationAgent
from app.agents.supervisor.tools import build_supervisor_context, evaluate_deterministically
from app.orchestration.action_executor import ActionExecutor
from app.orchestration.journey_engine import JourneyEngine
from app.models import Journey, JourneyStep, PathwayStep, PatientEvent
from app.audit.trace import record_agent_run
from app.core.config import settings

class SupervisorGraph:
    def __init__(self, db: Session):
        self.db = db
        self.graph = self._build()

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
            "execute": "execute",
            "wait": "wait",
            "escalate": "escalate",
        })
        builder.add_edge("journey_intelligence", "supervisor")
        builder.add_edge("coordination", "execute")
        builder.add_edge("execute", "supervisor")
        builder.add_edge("wait", END)
        builder.add_edge("escalate", END)
        return builder.compile()

    def _deterministic(self, state: SupervisorState):
        context = build_supervisor_context(self.db, UUID(state["journey_id"]))
        state["context"] = context or {}
        state["iteration"] = state.get("iteration", 0) + 1
        state["calls"] = state.get("calls", []) + [{"component": "deterministic_control_plane", "operation": "evaluate_journey"}]
        return state

    def _supervisor(self, state: SupervisorState):
        if state["iteration"] > settings.supervisor_max_iterations:
            state["decision"] = {"next_capability": "WAIT", "reason": "Maximum supervisor iterations reached"}
            state["calls"] = state.get("calls", []) + [{"component": "supervisor", "decision": state["decision"]}]
            return state
        agent = SupervisorAgent(self.db)
        decision = agent.decide(UUID(state["journey_id"]), state.get("context"))
        state["decision"] = decision
        state["calls"] = state.get("calls", []) + [{"component": agent.name, "decision": decision}]
        record_agent_run(self.db, UUID(state["journey_id"]), agent.name, agent.run_type, state.get("context", {}), decision, [], "SUCCESS")
        return state

    def _complete_agent_owned_step(self, journey_id, step_id, execution, meta):
        if execution.status != "SUCCESS" or meta.get("verified") is not True or not step_id:
            return False
        row = (
            self.db.query(JourneyStep, PathwayStep)
            .join(PathwayStep, JourneyStep.pathway_step_id == PathwayStep.id)
            .filter(JourneyStep.id == step_id, JourneyStep.journey_id == journey_id)
            .with_for_update()
            .first()
        )
        if not row:
            return False
        step, template = row
        journey = self.db.query(Journey).filter(Journey.id == journey_id).first()
        if not journey:
            return False
        if (step.owner_role or template.owner_role or "STAFF") != "AGENT":
            return False
        if step.status not in {"READY", "IN_PROGRESS"}:
            return False

        now = datetime.now(timezone.utc)
        step.status = "COMPLETED"
        step.completed_at = now
        step.block_reason = None
        step.updated_at = now
        self.db.add(PatientEvent(
            id=uuid4(),
            patient_id=journey.patient_id,
            journey_id=journey_id,
            event_type="STEP_COMPLETED",
            source="verified-agent-action",
            external_event_id=None,
            event_time=now,
            payload={
                "journey_step_id": str(step.id),
                "step_code": template.code,
                "owner_role": "AGENT",
                "step_completed": True,
                "verified": True,
                "action_execution_id": str(execution.id),
                "action_type": execution.action_type,
                "confirmation": "The assigned agent action completed successfully and passed verification.",
            },
            processed=True,
            created_at=now,
        ))
        JourneyEngine(self.db).evaluate(journey_id)
        return True

    def _route(self, state: SupervisorState):
        decision = state.get("decision", {})
        value = decision.get("next_capability", "WAIT")
        mapping = {
            "JOURNEY_INTELLIGENCE": "journey_intelligence",
            "COORDINATION": "coordination",
            "DETERMINISTIC": "wait",
            "WAIT": "wait",
            "ESCALATE": "escalate",
        }
        if value not in mapping:
            return "wait"
        return mapping[value]

    def _journey_intelligence(self, state: SupervisorState):
        agent = JourneyIntelligenceAgent(self.db)
        assessment, context = agent.assess(UUID(state["journey_id"]))
        output = assessment.model_dump()
        state["result"] = {"journey_intelligence": output}
        state["outcomes"] = state.get("outcomes", []) + [{"component": agent.name, "output": output}]
        state["context"] = {**state.get("context", {}), "journey_intelligence": output, "journey_context": context}
        state["iteration"] += 1
        state["calls"] = state.get("calls", []) + [{"component": agent.name, "output": output}]
        record_agent_run(self.db, UUID(state["journey_id"]), agent.name, agent.run_type, context, output, [], "SUCCESS")
        return state

    def _coordination(self, state: SupervisorState):
        decision = state.get("decision", {})
        step_id = decision.get("target_step_id")
        if not step_id:
            # Pick the first ready/blocked step from the deterministic context.
            for step in state.get("context", {}).get("steps", []):
                if step.get("ready") or step.get("blocked"):
                    step_id = step.get("journey_step_id"); decision["target_step_id"] = step_id; break
        step = next((s for s in state.get("context", {}).get("steps", []) if s.get("journey_step_id") == step_id), None)
        if not step:
            state["decision"] = {"next_capability": "WAIT", "reason": "No actionable step found"}
            state["calls"] = state.get("calls", []) + [{"component": "coordination", "outcome": "WAIT", "reason": state["decision"]["reason"]}]
            return state
        agent = CoordinationAgent(self.db)
        coord = agent.choose_action(UUID(state["journey_id"]), {
            "journey_step_id": step_id,
            "step_code": step.get("step_code"),
            "step_type": step.get("step_type"),
            "blocked": step.get("blocked"),
            "reason": step.get("reason"),
            "supervisor_context": state.get("context"),
        })
        state["result"] = {"coordination": coord.model_dump()}
        state["outcomes"] = state.get("outcomes", []) + [{"component": agent.name, "output": coord.model_dump()}]
        state["decision"] = {**decision, "action_type": coord.action_type, "payload": coord.payload}
        state["calls"] = state.get("calls", []) + [{"component": agent.name, "output": coord.model_dump()}]
        record_agent_run(self.db, UUID(state["journey_id"]), agent.name, agent.run_type, state.get("context", {}), coord.model_dump(), [], "SUCCESS")
        return state

    def _execute(self, state: SupervisorState):
        decision = state.get("decision", {})
        action_type = decision.get("action_type")
        if decision.get("next_capability") == "DETERMINISTIC":
            state["result"] = {"deterministic": evaluate_deterministically(self.db, UUID(state["journey_id"]))}
            state["outcomes"] = state.get("outcomes", []) + [{"component": "deterministic_control_plane", "output": state["result"]["deterministic"]}]
            return state
        if not action_type:
            state["decision"] = {"next_capability": "WAIT", "reason": "No action selected"}
            state["calls"] = state.get("calls", []) + [{"component": "action_executor", "outcome": "WAIT", "reason": state["decision"]["reason"]}]
            return state
        step_id = decision.get("target_step_id")
        executor = ActionExecutor(self.db)
        execution, meta = executor.execute(UUID(state["journey_id"]), UUID(step_id) if step_id else None, action_type, decision.get("payload") or {}, requested_by="SUPERVISOR")
        step_completed = self._complete_agent_owned_step(
            UUID(state["journey_id"]),
            UUID(step_id) if step_id else None,
            execution,
            meta,
        )
        state["result"] = {"action_execution": {"id": str(execution.id), "status": execution.status, "action_type": execution.action_type, "response": execution.response_payload, **meta}}
        state["result"]["action_execution"]["step_completed"] = step_completed
        state["outcomes"] = state.get("outcomes", []) + [{"component": "action_executor", "output": state["result"]["action_execution"]}]
        state["calls"] = state.get("calls", []) + [{"component": "action_executor", "output": state["result"]["action_execution"]}]
        state["iteration"] = state.get("iteration", 0) + 1
        self.db.commit()
        return state

    def _wait(self, state: SupervisorState):
        state["status"] = "WAIT"
        state["calls"] = state.get("calls", []) + [{"component": "supervisor", "outcome": "WAIT", "reason": state.get("decision", {}).get("reason")}]
        if state.get("decision", {}).get("next_capability") == "DETERMINISTIC":
            state["result"] = {"deterministic": evaluate_deterministically(self.db, UUID(state["journey_id"]))}
            state["outcomes"] = state.get("outcomes", []) + [{"component": "deterministic_control_plane", "output": state["result"]["deterministic"]}]
        return state

    def _escalate(self, state: SupervisorState):
        state["status"] = "ESCALATE"
        state["calls"] = state.get("calls", []) + [{"component": "supervisor", "outcome": "ESCALATE", "reason": state.get("decision", {}).get("reason")}]
        return state

    def run(self, journey_id):
        started_at = datetime.now(timezone.utc)
        state: SupervisorState = {"journey_id": str(journey_id), "iteration": 0, "calls": [], "outcomes": [], "status": "RUNNING"}
        try:
            result = self.graph.invoke(state, config={"recursion_limit": settings.supervisor_max_iterations * 3 + 5})
        except Exception as exc:
            self.db.rollback()
            record_agent_run(
                self.db, journey_id, "Orchestration", "ORCHESTRATION",
                {"journey_id": str(journey_id)}, None, [], "FAILED",
                error_message=str(exc), started_at=started_at,
            )
            self.db.commit()
            raise
        run = record_agent_run(
            self.db, journey_id, "Orchestration", "ORCHESTRATION",
            {"journey_id": str(journey_id)},
            {"decision": result.get("decision"), "result": result.get("result"), "outcomes": result.get("outcomes", [])},
            result.get("calls", []), result.get("status", "COMPLETED"), started_at=started_at,
        )
        self.db.commit()
        result["run_id"] = str(run.id)
        return result
