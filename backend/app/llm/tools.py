"""
Chat assistant tool registry.

The LLM never performs anything by itself: each tool call proposed by the model
is validated and executed server-side with the *user's own* authorization
context (same helpers as the REST API), so role checks always apply.

Two-step confirmation: tools with `requires_confirmation=True` are stored as a
pending action on an assistant message and only run after the user confirms in
chat. Read-only tools run immediately.
"""
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.authorization import (
    get_journey_for_action,
    get_journey_scoped,
    get_owned_patient,
    scope_patient_ids,
)
from app.models import Journey, JourneyStep, Patient, PatientEvent
from app.models.user import User


class ToolValidationError(Exception):
    """Raised when LLM-proposed tool arguments fail validation."""


# ---------------------------------------------------------------------------
# Parameter validation (LLM output is untrusted)
# ---------------------------------------------------------------------------

def _require_dict(args: Any) -> dict[str, Any]:
    if not isinstance(args, dict):
        raise ToolValidationError("Tool arguments must be a JSON object")
    return args


def _enum(value: Any, allowed: tuple[str, ...], field: str) -> str:
    if not isinstance(value, str) or value.strip().upper() not in allowed:
        raise ToolValidationError(f"{field} must be one of: {', '.join(allowed)}")
    return value.strip().upper()


def _uuid(value: Any, field: str) -> UUID:
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        raise ToolValidationError(f"{field} must be a valid id")


def _text(value: Any, field: str, *, max_len: int = 2000) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ToolValidationError(f"{field} must be non-empty text")
    return value.strip()[:max_len]


def _int(value: Any, field: str, lo: int, hi: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ToolValidationError(f"{field} must be an integer")
    if not lo <= value <= hi:
        raise ToolValidationError(f"{field} must be between {lo} and {hi}")
    return value


def _datetime_or_now(value: Any, field: str) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if not isinstance(value, str):
        raise ToolValidationError(f"{field} must be an ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ToolValidationError(f"{field} must be an ISO-8601 timestamp")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


# ---------------------------------------------------------------------------
# Executors — always called with the requesting user's identity.
# ---------------------------------------------------------------------------

def _serialize_journey(j: Journey, patient: Patient | None) -> dict[str, Any]:
    return {
        "id": str(j.id),
        "patient_id": str(j.patient_id),
        "status": (j.status or "").lower(),
        "priority": (j.priority or "").lower(),
        "started_at": j.started_at.isoformat() if j.started_at else None,
        "pathway_version": j.pathway_version,
        "patient_name": f"{patient.first_name} {patient.last_name}" if patient else None,
        "patient_reference": patient.patient_reference if patient else None,
    }


def _journeys_in_scope(db: Session, user: User) -> list[Journey]:
    q = db.query(Journey).order_by(Journey.updated_at.desc()).limit(25)
    ids = scope_patient_ids(db, user)
    if ids is not None:
        q = q.filter(Journey.patient_id.in_(ids))
    return q.all()


def _patient_by_id(db: Session, patient_id: UUID) -> Patient | None:
    return db.query(Patient).filter(Patient.id == patient_id).first()


def tool_list_journeys(db: Session, user: User, args: dict[str, Any]) -> dict[str, Any]:
    args = _require_dict(args)
    journeys = _journeys_in_scope(db, user)
    return {
        "tool": "list_journeys",
        "summary": f"Found {len(journeys)} journeys.",
        "data": {"journeys": [_serialize_journey(j, _patient_by_id(db, j.patient_id)) for j in journeys]},
    }


def tool_get_journey_steps(db: Session, user: User, args: dict[str, Any]) -> dict[str, Any]:
    args = _require_dict(args)
    journey_id = _uuid(args.get("journey_id"), "journey_id")
    journey = get_journey_scoped(journey_id, db, user)
    steps = (
        db.query(JourneyStep)
        .filter(JourneyStep.journey_id == journey.id)
        .order_by(JourneyStep.due_at)
        .limit(100)
        .all()
    )
    return {
        "tool": "get_journey_steps",
        "summary": f"Journey {str(journey.id)[:8]} has {len(steps)} steps.",
        "data": {
            "journey": _serialize_journey(journey, _patient_by_id(db, journey.patient_id)),
            "steps": [
                {
                    "id": str(s.id),
                    "status": (s.status or "").lower(),
                    "due_at": s.due_at.isoformat() if s.due_at else None,
                    "completed_at": s.completed_at.isoformat() if s.completed_at else None,
                    "block_reason": s.block_reason,
                }
                for s in steps
            ],
        },
    }


def tool_submit_event(db: Session, user: User, args: dict[str, Any]) -> dict[str, Any]:
    args = _require_dict(args)
    journey_id = _uuid(args.get("journey_id"), "journey_id")
    event_type = _text(args.get("event_type"), "event_type", max_len=100).upper()
    comment = _text(args.get("comment", ""), "comment", max_len=4000)

    allowed_types = {"SYMPTOM_REPORTED", "APPOINTMENT_PREFERENCE", "DOCUMENT_UPLOADED", "GENERAL_UPDATE", "QUESTION_ASKED",
                     "MEDICATION_TAKEN", "VITALS_RECORDED", "ATTENDANCE_CONFIRMED", "TASK_COMPLETED", "STATUS_REPORT"}
    if event_type not in allowed_types:
        raise ToolValidationError(
            "event_type must be one of: " + ", ".join(sorted(allowed_types))
        )

    if user.role == "PATIENT":
        # Same guarantees as POST /me/journeys/{id}/events.
        patient_id = get_owned_patient(user)
        journey = db.query(Journey).filter(Journey.id == journey_id).first()
        if not journey or journey.patient_id != patient_id:
            raise ToolValidationError("Journey not found among your journeys")
        source = "patient-portal"
        processed = False
    elif user.role in ("ADMIN", "CLINICIAN", "CARE_COORDINATOR"):
        # Staff go through the same path as POST /journeys/{id}/events.
        journey = get_journey_for_action(journey_id, db, user)
        source = "carepath-ui"
        processed = False
    else:
        raise ToolValidationError("Role cannot submit events")

    from app.orchestration.event_processor import EventProcessor
    event, _result = EventProcessor(db).ingest(
        journey.id, event_type, source, datetime.now(timezone.utc), {"comment": comment}, None
    )
    return {
        "tool": "submit_event",
        "summary": (
            f"Recorded a {event_type} event on journey {str(journey.id)[:8]} "
            f"({source})."
        ),
        "data": {
            "event_id": str(event.id),
            "event_type": event.event_type,
            "source": event.source,
            "journey_id": str(journey.id),
        },
    }


def tool_orchestrate_journey(db: Session, user: User, args: dict[str, Any]) -> dict[str, Any]:
    args = _require_dict(args)
    journey_id = _uuid(args.get("journey_id"), "journey_id")
    journey = get_journey_for_action(journey_id, db, user)
    from app.orchestration.journey_engine import JourneyEngine
    result = JourneyEngine(db).evaluate(journey.id)
    if not result:
        raise ToolValidationError("Journey not found")
    db.commit()
    db.refresh(result["journey"])
    return {
        "tool": "orchestrate_journey",
        "summary": f"Re-evaluated journey {str(journey.id)[:8]}.",
        "data": {
            "journey_id": str(journey.id),
            "status": (result["journey"].status or "").lower(),
            "steps_updated": len(result.get("steps", [])),
        },
    }


TOOL_NAMES = ("list_journeys", "get_journey_steps", "submit_event", "orchestrate_journey")

TOOL_EXECUTORS = {
    "list_journeys": tool_list_journeys,
    "get_journey_steps": tool_get_journey_steps,
    "submit_event": tool_submit_event,
    "orchestrate_journey": tool_orchestrate_journey,
}

# Two-step confirmation: the assistant proposes, the user confirms in chat,
# only then the executor runs.
TOOLS_REQUIRING_CONFIRMATION = {"submit_event", "orchestrate_journey"}

# Tools each role may propose. Patients get a patient-safe subset; staff get
# everything. Validation of *ownership* happens at execution time regardless.
ROLE_TOOL_ALLOWLIST: dict[str, tuple[str, ...]] = {
    "PATIENT": ("list_journeys", "get_journey_steps", "submit_event"),
    "ADMIN": TOOL_NAMES,
    "CLINICIAN": TOOL_NAMES,
    "CARE_COORDINATOR": TOOL_NAMES,
}

# OpenAI-compatible tool schemas handed to the LLM (subset per request role).
OPENAI_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_journeys",
            "description": "List journeys visible to the current user (most recent first).",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_journey_steps",
            "description": "Get the steps (and their statuses) of one journey.",
            "parameters": {
                "type": "object",
                "properties": {"journey_id": {"type": "string"}},
                "required": ["journey_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "submit_event",
            "description": (
                "Submit an update/event on a patient journey (symptom report, "
                "general update, question, appointment preference, etc.). "
                "Requires confirmation before it is applied."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "journey_id": {"type": "string"},
                    "event_type": {
                        "type": "string",
                        "description": "One of SYMPTOM_REPORTED, APPOINTMENT_PREFERENCE, "
                        "DOCUMENT_UPLOADED, GENERAL_UPDATE, QUESTION_ASKED, MEDICATION_TAKEN, "
                        "VITALS_RECORDED, ATTENDANCE_CONFIRMED, TASK_COMPLETED, STATUS_REPORT",
                    },
                    "comment": {"type": "string"},
                },
                "required": ["journey_id", "event_type", "comment"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "orchestrate_journey",
            "description": (
                "Re-run journey orchestration/evaluation for a journey. "
                "Requires confirmation before it is applied."
            ),
            "parameters": {
                "type": "object",
                "properties": {"journey_id": {"type": "string"}},
                "required": ["journey_id"],
            },
        },
    },
]


def tools_for_role(role: str) -> list[dict[str, Any]]:
    allowed = ROLE_TOOL_ALLOWLIST.get(role, ())
    return [t for t in OPENAI_TOOLS if t["function"]["name"] in allowed]


def toolRequiresConfirmation(name: str) -> bool:
    return name in TOOLS_REQUIRING_CONFIRMATION


def execute_tool(db: Session, user: User, name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Validate role + args, then run the tool with the user's authorization."""
    if name not in TOOL_EXECUTORS:
        raise ToolValidationError(f"Unknown tool: {name}")
    if name not in ROLE_TOOL_ALLOWLIST.get(user.role, ()):
        raise ToolValidationError("Your role cannot use this action")
    return TOOL_EXECUTORS[name](db, user, args)
