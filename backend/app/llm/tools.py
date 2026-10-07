"""
Chat assistant tool registry.

The LLM never performs anything by itself: each tool call proposed by the model
is validated and executed server-side with the *user's own* authorization
context (same helpers as the REST API), so role checks always apply.

Two-step confirmation: tools with `requires_confirmation=True` are stored as a
pending action on an assistant message and only run after the user confirms in
chat. Read-only tools run immediately. Mutating executors call the SAME service
layer as the REST API (app.services.journey_service, orchestration engines) —
business logic is never duplicated inside the chatbot.
"""
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.authorization import (
    STAFF_ROLES,
    get_journey_for_action,
    get_journey_scoped,
    get_owned_patient,
    scope_patient_ids,
)
from app.models import Journey, JourneyStep, Patient, Pathway, PathwayStep
from app.models.user import User
from app.services.journey_service import (
    pathway_steps,
    start_journey_for_patient,
)


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
# Shared serialization helpers
# ---------------------------------------------------------------------------

def _patient_name(p: Patient | None) -> str | None:
    return f"{p.first_name} {p.last_name}" if p else None


def _patient_ref(p: Patient) -> dict[str, Any]:
    return {
        "id": str(p.id),
        "name": _patient_name(p),
        "reference": p.patient_reference,
    }


def _patient_by_id(db: Session, patient_id: UUID) -> Patient | None:
    return db.query(Patient).filter(Patient.id == patient_id).first()


def _serialize_journey(j: Journey, patient: Patient | None, pathway_name: str | None = None) -> dict[str, Any]:
    return {
        "id": str(j.id),
        "patient_id": str(j.patient_id),
        "status": (j.status or "").lower(),
        "priority": (j.priority or "").lower(),
        "started_at": j.started_at.isoformat() if j.started_at else None,
        "pathway_version": j.pathway_version,
        "patient_name": _patient_name(patient),
        "patient_reference": patient.patient_reference if patient else None,
        "pathway_name": pathway_name,
    }


def _pathway_name_map(db: Session, pathway_ids: set[UUID]) -> dict[UUID, str]:
    if not pathway_ids:
        return {}
    rows = db.query(Pathway).filter(Pathway.id.in_(pathway_ids)).all()
    return {p.id: p.name for p in rows}


def _serialize_step(step: JourneyStep, template: PathwayStep | None) -> dict[str, Any]:
    return {
        "id": str(step.id),
        "name": template.name if template else None,
        "sequence_number": template.sequence_number if template else None,
        "status": (step.status or "").lower(),
        "due_at": step.due_at.isoformat() if step.due_at else None,
        "completed_at": step.completed_at.isoformat() if step.completed_at else None,
        "block_reason": step.block_reason,
    }


def _journeys_in_scope(db: Session, user: User, patient_id: UUID | None = None) -> list[Journey]:
    q = db.query(Journey)
    if patient_id is not None:
        q = q.filter(Journey.patient_id == patient_id)
    else:
        ids = scope_patient_ids(db, user)
        if ids is not None:
            q = q.filter(Journey.patient_id.in_(ids))
    return q.order_by(Journey.updated_at.desc()).limit(25).all()


def _patient_in_scope(db: Session, user: User, patient_id: UUID) -> Patient:
    """Patient row the user may read, else ToolValidationError (404-equivalent)."""
    ids = scope_patient_ids(db, user)
    if ids is not None and patient_id not in ids:
        raise ToolValidationError("Patient not found in your scope")
    patient = _patient_by_id(db, patient_id)
    if not patient:
        raise ToolValidationError("Patient not found")
    return patient


def _staff_required(user: User) -> None:
    if user.role not in STAFF_ROLES:
        raise ToolValidationError("Only care team members can use this action")


def _require_patient_id_in_scope(db: Session, user: User, args: dict[str, Any]) -> UUID:
    """Resolve the target patient: staff pass patient_id; patients are pinned to their own record."""
    if user.role == "PATIENT":
        return get_owned_patient(user)
    raw = args.get("patient_id")
    if raw is None:
        raise ToolValidationError("patient_id is required")
    patient_id = _uuid(raw, "patient_id")
    ids = scope_patient_ids(db, user)
    if ids is not None and patient_id not in ids:
        raise ToolValidationError("Patient not found in your scope")
    return patient_id


# ---------------------------------------------------------------------------
# Read tools — always run with the requesting user's authorization.
# ---------------------------------------------------------------------------

def tool_search_patients(db: Session, user: User, args: dict[str, Any]) -> dict[str, Any]:
    """Staff-only directory search so the assistant can resolve names like 'Vansh'."""
    args = _require_dict(args)
    _staff_required(user)
    query = _text(args.get("query"), "query", max_len=120)
    term = f"%{query}%"
    q = (
        db.query(Patient)
        .filter(
            Patient.first_name.ilike(term)
            | Patient.last_name.ilike(term)
            | Patient.patient_reference.ilike(term)
        )
        .order_by(Patient.first_name, Patient.last_name)
        .limit(10)
    )
    ids = scope_patient_ids(db, user)
    if ids is not None:
        q = q.filter(Patient.id.in_(ids))
    matches = q.all()
    return {
        "tool": "search_patients",
        "summary": f"Found {len(matches)} patient(s) matching \"{query}\"." if matches
        else f"No patients match \"{query}\".",
        "data": {"patients": [_patient_ref(p) for p in matches]},
    }


def tool_get_patient_summary(db: Session, user: User, args: dict[str, Any]) -> dict[str, Any]:
    """Patient identity + their journeys. Patients can only ever get their own."""
    args = _require_dict(args)
    patient_id = _require_patient_id_in_scope(db, user, args)
    patient = _patient_by_id(db, patient_id)
    if not patient:
        raise ToolValidationError("Patient not found")

    journeys = _journeys_in_scope(db, user, patient_id=patient_id)
    pathway_names = _pathway_name_map(db, {j.pathway_id for j in journeys})
    summary = {
        "id": str(patient.id),
        "name": _patient_name(patient),
        "reference": patient.patient_reference,
    }
    if user.role in STAFF_ROLES:
        summary["date_of_birth"] = patient.date_of_birth.isoformat() if patient.date_of_birth else None
        summary["gender"] = patient.gender
    return {
        "tool": "get_patient_summary",
        "summary": f"Patient {summary['name']} ({summary['reference']}) has {len(journeys)} journey(s).",
        "data": {
            "patient": summary,
            "journeys": [
                _serialize_journey(j, patient, pathway_names.get(j.pathway_id))
                for j in journeys
            ],
        },
    }


def tool_list_pathways(db: Session, user: User, args: dict[str, Any]) -> dict[str, Any]:
    """Staff-only: active pathway templates the assistant may propose starting."""
    args = _require_dict(args)
    _staff_required(user)
    pathways = (
        db.query(Pathway)
        .filter(Pathway.status == "ACTIVE")
        .order_by(Pathway.name)
        .all()
    )
    data = []
    for pathway in pathways:
        templates = pathway_steps(db, pathway.id)
        data.append({
            "id": str(pathway.id),
            "code": pathway.code,
            "name": pathway.name,
            "description": pathway.description,
            "steps": [t.name for t in templates],
        })
    return {
        "tool": "list_pathways",
        "summary": f"{len(data)} active pathway(s) available.",
        "data": {"pathways": data},
    }


def tool_list_journeys(db: Session, user: User, args: dict[str, Any]) -> dict[str, Any]:
    args = _require_dict(args)
    journeys = _journeys_in_scope(db, user)
    pathway_names = _pathway_name_map(db, {j.pathway_id for j in journeys})
    return {
        "tool": "list_journeys",
        "summary": f"Found {len(journeys)} journeys.",
        "data": {
            "journeys": [
                _serialize_journey(j, _patient_by_id(db, j.patient_id), pathway_names.get(j.pathway_id))
                for j in journeys
            ]
        },
    }


def tool_get_journey_steps(db: Session, user: User, args: dict[str, Any]) -> dict[str, Any]:
    args = _require_dict(args)
    journey_id = _uuid(args.get("journey_id"), "journey_id")
    journey = get_journey_scoped(journey_id, db, user)
    rows = (
        db.query(JourneyStep, PathwayStep)
        .join(PathwayStep, JourneyStep.pathway_step_id == PathwayStep.id)
        .filter(JourneyStep.journey_id == journey.id)
        .order_by(PathwayStep.sequence_number)
        .limit(100)
        .all()
    )
    pathway = db.query(Pathway).filter(Pathway.id == journey.pathway_id).first()
    return {
        "tool": "get_journey_steps",
        "summary": f"Journey {str(journey.id)[:8]} has {len(rows)} steps.",
        "data": {
            "journey": _serialize_journey(
                journey,
                _patient_by_id(db, journey.patient_id),
                pathway.name if pathway else None,
            ),
            "steps": [_serialize_step(step, template) for step, template in rows],
        },
    }


def tool_get_pending_tasks(db: Session, user: User, args: dict[str, Any]) -> dict[str, Any]:
    """Open (pending/ready/in-progress/blocked) steps across the user's scope."""
    args = _require_dict(args)
    patient_id = _require_patient_id_in_scope(db, user, args) if (
        user.role == "PATIENT" or args.get("patient_id")
    ) else None

    q = (
        db.query(JourneyStep, PathwayStep, Journey)
        .join(PathwayStep, JourneyStep.pathway_step_id == PathwayStep.id)
        .join(Journey, JourneyStep.journey_id == Journey.id)
        .filter(JourneyStep.status.in_(("PENDING", "READY", "IN_PROGRESS", "BLOCKED")))
    )
    if patient_id is not None:
        q = q.filter(Journey.patient_id == patient_id)
    else:
        ids = scope_patient_ids(db, user)
        if ids is not None:
            q = q.filter(Journey.patient_id.in_(ids))
    rows = q.order_by(Journey.updated_at.desc(), PathwayStep.sequence_number).limit(100).all()

    pathway_names = _pathway_name_map(db, {journey.pathway_id for _, _, journey in rows})
    patient_ids = {journey.patient_id for _, _, journey in rows}
    patient_names = {
        p.id: _patient_name(p)
        for p in db.query(Patient).filter(Patient.id.in_(patient_ids)).all()
    } if patient_ids else {}

    by_journey: dict[str, dict[str, Any]] = {}
    for step, template, journey in rows:
        entry = by_journey.setdefault(
            str(journey.id),
            {
                "journey_id": str(journey.id),
                "patient_name": patient_names.get(journey.patient_id),
                "pathway_name": pathway_names.get(journey.pathway_id),
                "tasks": [],
            },
        )
        entry["tasks"].append(_serialize_step(step, template))

    total = sum(len(e["tasks"]) for e in by_journey.values())
    return {
        "tool": "get_pending_tasks",
        "summary": f"{total} open task(s) across {len(by_journey)} journey(s).",
        "data": {"journeys": list(by_journey.values())},
    }


# ---------------------------------------------------------------------------
# Action tools — require_confirmation, executed only after user confirmation.
# ---------------------------------------------------------------------------

def tool_start_pathway(db: Session, user: User, args: dict[str, Any]) -> dict[str, Any]:
    """
    Start a pathway journey for a patient. Staff-only; runs the same service
    function as POST /patients/{id}/journeys so business rules are identical.
    """
    args = _require_dict(args)
    _staff_required(user)
    patient_id = _uuid(args.get("patient_id"), "patient_id")
    pathway_id = _uuid(args.get("pathway_id"), "pathway_id")
    priority = _enum(args.get("priority", "MEDIUM"), ("CRITICAL", "HIGH", "MEDIUM", "LOW"), "priority")

    patient = _patient_in_scope(db, user, patient_id)
    journey = start_journey_for_patient(db, patient_id, pathway_id, priority)
    db.commit()
    db.refresh(journey)

    pathway = db.query(Pathway).filter(Pathway.id == pathway_id).first()
    next_steps = [
        template.name
        for template in pathway_steps(db, pathway_id)[:3]
    ]
    return {
        "tool": "start_pathway",
        "summary": (
            f"{pathway.name if pathway else 'Pathway'} started successfully for "
            f"{_patient_name(patient)}."
        ),
        "data": {
            "journey": _serialize_journey(
                journey, patient,
                pathway.name if pathway else None,
            ),
            "next_steps": next_steps,
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
    elif user.role in STAFF_ROLES:
        # Staff go through the same path as POST /journeys/{id}/events.
        journey = get_journey_for_action(journey_id, db, user)
        source = "carepath-ui"
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


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

TOOL_NAMES = (
    "search_patients", "get_patient_summary", "list_pathways",
    "list_journeys", "get_journey_steps", "get_pending_tasks",
    "start_pathway", "submit_event", "orchestrate_journey",
)

TOOL_EXECUTORS = {
    "search_patients": tool_search_patients,
    "get_patient_summary": tool_get_patient_summary,
    "list_pathways": tool_list_pathways,
    "list_journeys": tool_list_journeys,
    "get_journey_steps": tool_get_journey_steps,
    "get_pending_tasks": tool_get_pending_tasks,
    "start_pathway": tool_start_pathway,
    "submit_event": tool_submit_event,
    "orchestrate_journey": tool_orchestrate_journey,
}

# Two-step confirmation: the assistant proposes, the user confirms in chat,
# only then the executor runs.
TOOLS_REQUIRING_CONFIRMATION = {"start_pathway", "submit_event", "orchestrate_journey"}

READ_ONLY_TOOLS = set(TOOL_NAMES) - TOOLS_REQUIRING_CONFIRMATION

# Tools each role may propose. Patients get a patient-safe subset; staff get
# everything. Validation of *ownership* happens at execution time regardless.
ROLE_TOOL_ALLOWLIST: dict[str, tuple[str, ...]] = {
    "PATIENT": (
        "list_journeys", "get_journey_steps", "get_patient_summary",
        "get_pending_tasks", "submit_event",
    ),
    "ADMIN": TOOL_NAMES,
    "CLINICIAN": TOOL_NAMES,
    "CARE_COORDINATOR": TOOL_NAMES,
}


def describe_action(db: Session, user: User, name: str, args: dict[str, Any]) -> dict[str, Any]:
    """
    Human-readable confirmation-card data for a pending action. Best-effort:
    description failures never block the action itself (raw ids are shown
    as fallback in the UI).
    """
    description: dict[str, Any] = {"title": name.replace("_", " ").capitalize(), "changes": []}
    try:
        if name == "start_pathway":
            pathway = (
                db.query(Pathway).filter(Pathway.id == UUID(str(args.get("pathway_id")))).first()
                if args.get("pathway_id") else None
            )
            patient = _patient_by_id(db, UUID(str(args.get("patient_id")))) if args.get("patient_id") else None
            n_steps = len(pathway_steps(db, pathway.id)) if pathway else 0
            description.update({
                "title": f"Start {pathway.name}" if pathway else "Start pathway",
                "patient": _patient_name(patient),
                "patient_reference": patient.patient_reference if patient else None,
                "pathway": pathway.name if pathway else None,
                "priority": (args.get("priority") or "MEDIUM"),
                "changes": [
                    "Create the journey",
                    f"Initialize {n_steps} pathway stage{'s' if n_steps != 1 else ''}",
                    "Create the initial pending tasks",
                    "Set the journey status to Active",
                ],
            })
        elif name == "submit_event":
            journey = (
                db.query(Journey).filter(Journey.id == UUID(str(args.get("journey_id")))).first()
                if args.get("journey_id") else None
            )
            event_type = str(args.get("event_type") or "").replace("_", " ").lower()
            changes = [f"Record a {event_type or 'general'} event on the journey"]
            if args.get("comment"):
                changes.append(f"Attach note: \"{str(args['comment'])[:160]}\"")
            description.update({
                "title": "Record an update",
                "patient": _patient_name(_patient_by_id(db, journey.patient_id)) if journey else None,
                "changes": changes,
            })
        elif name == "orchestrate_journey":
            description.update({
                "title": "Re-evaluate journey",
                "changes": [
                    "Re-run the deterministic journey rules",
                    "Refresh step statuses, due dates and blockers",
                ],
            })
    except Exception:  # noqa: BLE001 — description is cosmetic only
        pass
    return description


# OpenAI-compatible tool schemas handed to the LLM (subset per request role).
OPENAI_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_patients",
            "description": (
                "Search patients by first/last name or reference id. Use this to "
                "resolve a patient mentioned by name before acting on them. If "
                "several patients match, ask the user which one they mean."
            ),
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_patient_summary",
            "description": "Get a patient's identity and their journeys (with statuses).",
            "parameters": {
                "type": "object",
                "properties": {"patient_id": {"type": "string"}},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_pathways",
            "description": "List the active care pathway templates and their steps.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
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
            "name": "get_pending_tasks",
            "description": (
                "Get open tasks (pending/ready/in-progress/blocked steps) for a "
                "patient's journeys, or across your whole scope."
            ),
            "parameters": {
                "type": "object",
                "properties": {"patient_id": {"type": "string"}},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "start_pathway",
            "description": (
                "Start an active care pathway for a patient: creates the journey, "
                "initializes its stages and pending tasks. Requires the patient_id "
                "and pathway_id (resolve them with search_patients / list_pathways "
                "first). Requires confirmation before it is applied."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_id": {"type": "string"},
                    "pathway_id": {"type": "string"},
                    "priority": {
                        "type": "string",
                        "description": "One of CRITICAL, HIGH, MEDIUM, LOW (default MEDIUM).",
                    },
                },
                "required": ["patient_id", "pathway_id"],
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


def isReadOnlyTool(name: str) -> bool:
    return name in READ_ONLY_TOOLS


def execute_tool(db: Session, user: User, name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Validate role + args, then run the tool with the user's authorization."""
    if name not in TOOL_EXECUTORS:
        raise ToolValidationError(f"Unknown tool: {name}")
    if name not in ROLE_TOOL_ALLOWLIST.get(user.role, ()):
        raise ToolValidationError("Your role cannot use this action")
    return TOOL_EXECUTORS[name](db, user, args)
