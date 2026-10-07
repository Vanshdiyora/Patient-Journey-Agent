"""
Human-readable report of one orchestration run: which steps changed and why,
what actions ran, and a one-paragraph summary for the UI.
"""
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import Journey, JourneyStep, PathwayStep
from app.orchestration.policy import ACTION_LABELS


def snapshot(db: Session, journey_id) -> dict[str, Any]:
    journey = db.query(Journey).filter(Journey.id == UUID(str(journey_id))).first()
    rows = (
        db.query(JourneyStep, PathwayStep)
        .join(PathwayStep, JourneyStep.pathway_step_id == PathwayStep.id)
        .filter(JourneyStep.journey_id == UUID(str(journey_id)))
        .order_by(PathwayStep.sequence_number)
        .all()
    )
    return {
        "journey_status": journey.status if journey else None,
        "steps": {
            str(step.id): {
                "name": template.name,
                "status": step.status,
                "owner_role": step.owner_role or template.owner_role,
                "block_reason": step.block_reason,
            }
            for step, template in rows
        },
    }


def _pretty(value: str | None) -> str:
    return (value or "").replace("_", " ").lower()


def step_changes(before: dict[str, Any], after: dict[str, Any], agent_completed: list[str]) -> list[dict[str, Any]]:
    changes = []
    for step_id, new in after["steps"].items():
        old = before["steps"].get(step_id)
        if not old or old["status"] == new["status"]:
            continue
        by_agent = step_id in agent_completed
        changes.append({
            "step_id": step_id,
            "step_name": new["name"],
            "from": old["status"],
            "to": new["status"],
            "changed_by": "agent_verified_action" if by_agent else "rules",
            "reason": (
                "The agent's action was executed and verified, and it fulfils this agent-owned step."
                if by_agent else
                new["block_reason"] if new["status"] == "BLOCKED" else
                "Dependencies are met and every earlier step is finished, so the rules marked it ready."
                if new["status"] == "READY" else
                "The rules re-evaluated the journey."
            ),
        })
    return changes


def build_summary(state: dict[str, Any], changes: list[dict[str, Any]], journey_change: dict[str, Any] | None) -> str:
    parts: list[str] = []
    if state.get("mode") == "RULES_ONLY":
        why = "; ".join(dict.fromkeys(state.get("warnings", []))) or "the AI was unavailable"
        parts.append(f"AI was not used ({why}) - the built-in rules made the decisions.")

    if changes:
        agent = [c for c in changes if c["changed_by"] != "rules"]
        rules = [c for c in changes if c["changed_by"] == "rules"]
        if rules:
            parts.append(f"Rules updated {len(rules)} step(s): " + ", ".join(
                f"{c['step_name']} ({_pretty(c['from'])} -> {_pretty(c['to'])})" for c in rules[:4]
            ) + ("..." if len(rules) > 4 else "") + ".")
        if agent:
            parts.append("The agent completed: " + ", ".join(c["step_name"] for c in agent) + ".")
    else:
        parts.append("No step status changed.")
    if journey_change:
        parts.append(f"Journey is now {_pretty(journey_change['to'])}.")

    for item in state.get("outcomes", []):
        if item.get("component") != "action_executor":
            continue
        out = item.get("output") or {}
        label = ACTION_LABELS.get(out.get("action_type"), _pretty(out.get("action_type")).capitalize())
        simulated = out.get("delivery") == "mock"
        target = f" for '{out['step_name']}'" if out.get("step_name") else ""
        if out.get("awaiting_approval"):
            parts.append(f"{label}{target}: recorded and waiting for staff approval.")
        elif out.get("status") == "FAILED":
            parts.append(f"{label}{target} failed.")
        elif out.get("duplicate"):
            parts.append(f"{label}{target} was already sent earlier, so nothing new was sent.")
        else:
            parts.append(f"{label}{target} (simulated - email is not configured)." if simulated else f"{label}{target} (verified).")

    decision = state.get("decision") or {}
    final = state.get("status")
    if final == "ESCALATE":
        parts.append(f"Escalated to staff: {decision.get('reason') or 'attention needed'}")
    elif decision.get("reason"):
        parts.append(f"Stopped: {decision['reason']}")
    return " ".join(parts)
