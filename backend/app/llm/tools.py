"""
Chat assistant tool registry.

The LLM never performs anything by itself. Every tool is declared once here
(ToolSpec) with the roles allowed to use it, the parameters it needs, and
whether it needs the user's confirmation. The chat service then enforces, in
this order and entirely server-side:

  1. role permission   -> "You are not permitted to ..." (model is not asked)
  2. missing arguments -> a question back to the user (model is not asked)
  3. argument validation + scope checks (dry run, nothing is written)
  4. mutating tools   -> stored as a pending action; the user must confirm
  5. execution        -> role + scope are checked again at execution time

Read tools run immediately; they are functions over DB queries scoped to the
caller (see tool_read). Mutating tools reuse the REST handlers (see tool_write).
"""
from dataclasses import dataclass, field
from typing import Any, Callable

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.authorization import STAFF_ROLES
from app.llm import tool_read as read
from app.llm import tool_write as write
from app.llm.tool_helpers import (
    ToolPermissionError,
    ToolValidationError,
    bool_value,
    enum_value,
    int_value,
    patient_in_scope,
    readable_journey,
    text_value,
    uuid_value,
)
from app.models import ExceptionRecord, JourneyStep, Pathway, PathwayStep, User
from app.services.journey_service import find_active_journey

ALL_ROLES = ("PATIENT",) + STAFF_ROLES
STAFF = STAFF_ROLES
ADMIN = ("ADMIN",)
PATIENT = ("PATIENT",)

__all__ = [
    "ToolPermissionError", "ToolValidationError", "TOOL_SPECS", "get_spec", "is_allowed",
    "tools_for_llm", "toolRequiresConfirmation", "isReadOnlyTool", "missing_arguments",
    "prepare_arguments", "describe_action", "execute_tool", "denial_message",
    "missing_message", "role_capabilities",
]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    label: str                       # verb phrase used in user-facing messages
    description: str
    roles: tuple[str, ...]
    executor: Callable[[Session, Any, dict[str, Any]], dict[str, Any]]
    properties: dict[str, dict[str, Any]] = field(default_factory=dict)
    required: tuple[str, ...] = ()
    confirm: bool = False
    # How to ask the user for each required parameter (plain language, no ids).
    ask: dict[str, str] = field(default_factory=dict)


def _s(description: str, **extra) -> dict[str, Any]:
    return {"type": "string", "description": description, **extra}


JOURNEY_ID = _s("Journey id (UUID). Get it from list_journeys / get_patient_summary.")
PATIENT_ID = _s("Patient id (UUID). Resolve a name with search_patients first.")
STEP_ID = _s("Journey step id (UUID). Get it from get_journey_steps.")
PRIORITY = _s("One of CRITICAL, HIGH, MEDIUM, LOW (default MEDIUM).", enum=["CRITICAL", "HIGH", "MEDIUM", "LOW"])

_STAFF_EVENTS = ", ".join(write.STAFF_EVENT_TYPES)
_PATIENT_EVENTS = ", ".join(write.PATIENT_EVENT_TYPES)

SPECS: tuple[ToolSpec, ...] = (
    # ----- read -----------------------------------------------------------
    ToolSpec(
        "search_patients", "search the patient directory",
        "Search patients by first/last name or reference id. Use it to resolve a patient mentioned by "
        "name before acting on them. If several match, ask the user which one.",
        STAFF, read.tool_search_patients,
        {"query": _s("Name or patient reference to search for")}, ("query",),
        ask={"query": "which patient (name or patient reference)"},
    ),
    ToolSpec(
        "list_patients", "list patients",
        "List patients in the user's scope (most recent first).",
        STAFF, read.tool_list_patients,
        {"limit": {"type": "integer", "minimum": 1, "maximum": 50, "description": "How many (default 20)"}},
    ),
    ToolSpec(
        "get_patient_summary", "view a patient's summary",
        "Get a patient's identity and their journeys. Patients get their own record; staff must pass patient_id.",
        ALL_ROLES, read.tool_get_patient_summary,
        {"patient_id": PATIENT_ID},
    ),
    ToolSpec(
        "list_pathways", "list care pathways",
        "List the active care pathway templates with their steps.",
        STAFF, read.tool_list_pathways,
    ),
    ToolSpec(
        "list_journeys", "list journeys",
        "List journeys visible to the user (most recent first), optionally filtered.",
        ALL_ROLES, read.tool_list_journeys,
        {
            "status": _s("ACTIVE, BLOCKED, COMPLETED or CANCELLED", enum=list(read.JOURNEY_STATUSES)),
            "priority": _s("CRITICAL, HIGH, MEDIUM or LOW", enum=list(read.PRIORITIES)),
            "patient_id": _s("Only this patient's journeys (staff only)."),
        },
    ),
    ToolSpec(
        "get_journey_steps", "view a journey's steps",
        "Get the steps (and their statuses, owners, due dates) of one journey.",
        ALL_ROLES, read.tool_get_journey_steps,
        {"journey_id": JOURNEY_ID}, ("journey_id",),
        ask={"journey_id": "which journey (patient name, pathway, or journey id)"},
    ),
    ToolSpec(
        "get_journey_events", "view a journey's recent events",
        "Get the most recent events/updates recorded on a journey.",
        ALL_ROLES, read.tool_get_journey_events,
        {"journey_id": JOURNEY_ID, "limit": {"type": "integer", "minimum": 1, "maximum": 50}},
        ("journey_id",),
        ask={"journey_id": "which journey (patient name, pathway, or journey id)"},
    ),
    ToolSpec(
        "get_pending_tasks", "view open tasks",
        "Get open tasks (pending/ready/in-progress/blocked steps) for one patient or the whole scope.",
        ALL_ROLES, read.tool_get_pending_tasks,
        {"patient_id": PATIENT_ID},
    ),
    ToolSpec(
        "get_dashboard_summary", "view the dashboard figures",
        "Get headline numbers: active/blocked journeys, open exceptions, pending steps, patient counts.",
        STAFF, read.tool_get_dashboard_summary,
    ),
    ToolSpec(
        "list_exceptions", "list exceptions",
        "List workflow exceptions (alerts), optionally filtered by status or severity.",
        STAFF, read.tool_list_exceptions,
        {
            "status": _s("OPEN, IN_PROGRESS, RESOLVED or DISMISSED", enum=list(read.EXCEPTION_STATUSES)),
            "severity": _s("CRITICAL, HIGH, MEDIUM or LOW", enum=list(read.PRIORITIES)),
        },
    ),
    ToolSpec(
        "list_users", "view user accounts",
        "List portal user accounts (find a user's id before changing their role or status).",
        ADMIN, read.tool_list_users,
        {
            "role": _s("Filter by role", enum=list(write.ROLES)),
            "search": _s("Name or email to search for"),
        },
    ),
    ToolSpec(
        "get_chat_audit", "view the chatbot audit trail",
        "Show the latest chatbot audit entries (who proposed/confirmed/executed/was denied what).",
        ADMIN, read.tool_get_chat_audit,
        {"limit": {"type": "integer", "minimum": 1, "maximum": 25}},
    ),
    # ----- mutations (always confirmed by the user first) ------------------
    ToolSpec(
        "start_pathway", "start a care pathway for a patient",
        "Start an active care pathway for a patient: creates the journey, its stages and pending tasks. "
        "Requires user confirmation.",
        STAFF, write.tool_start_pathway,
        {"patient_id": PATIENT_ID, "pathway_id": _s("Pathway id (UUID). Get it from list_pathways."), "priority": PRIORITY},
        ("patient_id", "pathway_id"), confirm=True,
        ask={"patient_id": "which patient (name or patient reference)", "pathway_id": "which care pathway"},
    ),
    ToolSpec(
        "submit_event", "record an update on a journey",
        "Record an update/event on a journey (symptom report, general update, question, appointment "
        f"preference, ...). Patients may use: {_PATIENT_EVENTS}. Staff may also use: "
        f"{', '.join(write.STAFF_EVENT_TYPES[len(write.PATIENT_EVENT_TYPES):])}. Requires user confirmation.",
        ALL_ROLES, write.tool_submit_event,
        {"journey_id": JOURNEY_ID, "event_type": _s(f"One of {_STAFF_EVENTS}"), "comment": _s("The note to record")},
        ("journey_id", "event_type", "comment"), confirm=True,
        ask={
            "journey_id": "which journey this update is for",
            "event_type": "what kind of update this is (e.g. symptom report, general update, question)",
            "comment": "what the update should say",
        },
    ),
    ToolSpec(
        "complete_step", "mark a journey step as completed",
        "For staff only. Find the requested journey and step using get_journey_steps, then mark that "
        "specific step complete only if its status is READY or IN_PROGRESS and the signed-in staff "
        "role is authorized for its owner_role. Do not infer that the care task happened from the "
        "request alone; if the user has not stated it was actually performed, ask first. The app "
        "requires explicit confirmation in its action card before completion.",
        STAFF, write.tool_complete_step,
        {"journey_id": JOURNEY_ID, "step_id": STEP_ID}, ("journey_id", "step_id"), confirm=True,
        ask={"journey_id": "which journey", "step_id": "which step to complete"},
    ),
    ToolSpec(
        "submit_step_update", "report one of your tasks as done",
        "Patient only: tell the care team you finished one of your own tasks, with a short note. "
        "Requires user confirmation.",
        PATIENT, write.tool_submit_step_update,
        {"journey_id": JOURNEY_ID, "step_id": STEP_ID, "comment": _s("What you completed")},
        ("journey_id", "step_id", "comment"), confirm=True,
        ask={
            "journey_id": "which journey the task belongs to",
            "step_id": "which task you completed",
            "comment": "a short note describing what you completed",
        },
    ),
    ToolSpec(
        "update_step_time_limit", "change a step's time limit",
        "Change the time limit (hours) of a journey step. Requires user confirmation.",
        STAFF, write.tool_update_step_time_limit,
        {
            "journey_id": JOURNEY_ID, "step_id": STEP_ID,
            "time_limit_hours": {"type": "integer", "minimum": 1, "maximum": 8760, "description": "New limit in hours"},
        },
        ("journey_id", "step_id", "time_limit_hours"), confirm=True,
        ask={
            "journey_id": "which journey", "step_id": "which step",
            "time_limit_hours": "the new time limit in hours",
        },
    ),
    ToolSpec(
        "orchestrate_journey", "run orchestration for a patient journey",
        "Run or re-evaluate journey orchestration for a patient journey. Requires user confirmation.",
        STAFF, write.tool_orchestrate_journey,
        {"journey_id": JOURNEY_ID}, ("journey_id",), confirm=True,
        ask={"journey_id": "which journey (patient name, pathway, or journey id)"},
    ),
    ToolSpec(
        "update_exception", "update an exception",
        "Change an exception's status (OPEN, IN_PROGRESS, RESOLVED, DISMISSED) with an optional note. "
        "Requires user confirmation.",
        STAFF, write.tool_update_exception,
        {
            "exception_id": _s("Exception id (UUID). Get it from list_exceptions."),
            "status": _s("OPEN, IN_PROGRESS, RESOLVED or DISMISSED", enum=list(write.EXCEPTION_STATUSES)),
            "recommended_action": _s("Optional note about the action taken"),
        },
        ("exception_id", "status"), confirm=True,
        ask={"exception_id": "which exception", "status": "the new status (open, in progress, resolved or dismissed)"},
    ),
    ToolSpec(
        "set_user_role", "change a user's role",
        "Change a portal user's role. Requires user confirmation.",
        ADMIN, write.tool_set_user_role,
        {"user_id": _s("User id (UUID). Get it from list_users."), "role": _s("New role", enum=list(write.ROLES))},
        ("user_id", "role"), confirm=True,
        ask={"user_id": "which user (name or email)", "role": "the new role (admin, clinician, care coordinator or patient)"},
    ),
    ToolSpec(
        "set_user_status", "activate or deactivate a user account",
        "Activate (is_active=true) or deactivate (false) a portal user's account. Requires user confirmation.",
        ADMIN, write.tool_set_user_status,
        {"user_id": _s("User id (UUID). Get it from list_users."), "is_active": {"type": "boolean"}},
        ("user_id", "is_active"), confirm=True,
        ask={"user_id": "which user (name or email)", "is_active": "whether to activate or deactivate the account"},
    ),
    ToolSpec(
        "create_pathway", "create a care pathway",
        "Create a new care pathway template with ordered steps. Requires user confirmation.",
        ADMIN, write.tool_create_pathway,
        {
            "code": _s("Short unique code, letters/numbers/_/-"),
            "name": _s("Pathway name"),
            "description": _s("Optional description"),
            "steps": {
                "type": "array",
                "description": "Ordered steps",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "code": {"type": "string"},
                        "step_type": {"type": "string", "description": "e.g. TASK, APPOINTMENT, FOLLOW_UP"},
                        "owner_role": {"type": "string", "description": "PATIENT, CLINICIAN, CARE_COORDINATOR, ADMIN, AGENT or STAFF"},
                        "time_limit_hours": {"type": "integer"},
                    },
                    "required": ["name", "time_limit_hours"],
                },
            },
        },
        ("code", "name", "steps"), confirm=True,
        ask={
            "code": "a short unique code for the pathway",
            "name": "the pathway name",
            "steps": "the steps (name and time limit in hours for each)",
        },
    ),
)

TOOL_SPECS: dict[str, ToolSpec] = {s.name: s for s in SPECS}


# ---------------------------------------------------------------------------
# Lookup / permission helpers
# ---------------------------------------------------------------------------

def get_spec(name: str) -> ToolSpec | None:
    return TOOL_SPECS.get(name)


def is_allowed(user, spec: ToolSpec) -> bool:
    return user.role in spec.roles


def toolRequiresConfirmation(name: str) -> bool:
    spec = TOOL_SPECS.get(name)
    return bool(spec and spec.confirm)


def isReadOnlyTool(name: str) -> bool:
    spec = TOOL_SPECS.get(name)
    return bool(spec and not spec.confirm)


def role_capabilities(role: str) -> tuple[list[str], list[str]]:
    """(things the role may do, things it may not do) as plain phrases."""
    allowed = [s.label for s in SPECS if role in s.roles]
    denied = [s.label for s in SPECS if role not in s.roles]
    return allowed, denied


def tools_for_llm() -> list[dict[str, Any]]:
    """
    Every tool is shown to the model whatever the user's role, so a request the
    role may not make still reaches the server-side gate and gets the standard
    "not permitted" answer instead of depending on the model to refuse.
    """
    tools = []
    for s in SPECS:
        who = "any signed-in user" if s.roles == ALL_ROLES else ", ".join(r.replace("_", " ").lower() for r in s.roles)
        tools.append({
            "type": "function",
            "function": {
                "name": s.name,
                "description": f"{s.description} (Allowed roles: {who}.)",
                "parameters": {"type": "object", "properties": s.properties, "required": list(s.required)},
            },
        })
    return tools


def denial_message(user, spec: ToolSpec | None, reason: str | None = None) -> str:
    action = spec.label if spec else "do this"
    role = user.role.replace("_", " ").lower()
    text = f"You are not permitted to {action}. Your role ({role}) does not have access to this task."
    if reason and reason not in text:
        text += f" ({reason})"
    return text


# ---------------------------------------------------------------------------
# Missing-information handling
# ---------------------------------------------------------------------------

def _autofill(db: Session, user, spec: ToolSpec, args: dict[str, Any]) -> dict[str, Any]:
    """A patient with exactly one journey does not need to name it."""
    args = dict(args)
    if user.role == "PATIENT" and "journey_id" in spec.properties and not args.get("journey_id") and user.patient_id:
        from app.models import Journey

        rows = db.query(Journey.id).filter(Journey.patient_id == user.patient_id).limit(2).all()
        if len(rows) == 1:
            args["journey_id"] = str(rows[0][0])
    return args


def missing_arguments(db: Session, user, spec: ToolSpec, args: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Returns (args with safe auto-fills, parameter names still missing)."""
    args = _autofill(db, user, spec, args if isinstance(args, dict) else {})
    missing = []
    for name in spec.required:
        value = args.get(name)
        blank = value is None or (isinstance(value, str) and not value.strip()) or value == [] or value == {}
        if blank:
            missing.append(name)
    return args, missing


def _choices(db: Session, name: str) -> str | None:
    if name == "pathway_id":
        names = [p.name for p in db.query(Pathway).filter(Pathway.status == "ACTIVE").order_by(Pathway.name).all()]
        return "Available pathways: " + ", ".join(names) + "." if names else None
    return None


def missing_message(db: Session, spec: ToolSpec, missing: list[str]) -> str:
    asks = [spec.ask.get(m, m.replace("_", " ")) for m in missing]
    if len(asks) == 1:
        body = asks[0]
    else:
        body = "; ".join(f"({i}) {a}" for i, a in enumerate(asks, 1))
    text = f"To {spec.label}, I still need to know: {body}. Could you tell me?"
    hints = [h for h in (_choices(db, m) for m in missing) if h]
    return text + (" " + " ".join(hints) if hints else "")


# ---------------------------------------------------------------------------
# Validation (dry run: nothing is written)
# ---------------------------------------------------------------------------

def _http_to_tool(exc: HTTPException) -> Exception:
    detail = str(exc.detail)
    if exc.status_code in (401, 403):
        return ToolPermissionError(detail)
    return ToolValidationError(detail)


def _normalize(spec: ToolSpec, args: dict[str, Any]) -> dict[str, Any]:
    clean: dict[str, Any] = {}
    for name, prop in spec.properties.items():
        value = args.get(name)
        if value is None or (isinstance(value, str) and not value.strip()):
            continue
        kind = prop.get("type")
        if kind == "string" and name.endswith("_id"):
            clean[name] = str(uuid_value(value, name))
        elif kind == "string" and "enum" in prop:
            clean[name] = enum_value(value, tuple(prop["enum"]), name)
        elif kind == "string":
            clean[name] = text_value(value, name, max_len=4000)
        elif kind == "integer":
            clean[name] = int_value(value, name, prop.get("minimum", 0), prop.get("maximum", 1_000_000))
        elif kind == "boolean":
            clean[name] = bool_value(value, name)
        else:
            clean[name] = value
    return clean


def _check_targets(db: Session, user, spec: ToolSpec, args: dict[str, Any]) -> None:
    """Scope + business pre-checks for mutating tools, mirroring the REST rules."""
    journey = None
    if "journey_id" in args:
        journey = readable_journey(db, user, uuid_value(args["journey_id"], "journey_id"))
    if user.role != "PATIENT" and "patient_id" in args:
        patient_in_scope(db, user, uuid_value(args["patient_id"], "patient_id"))

    if "step_id" in args:
        row = (
            db.query(JourneyStep, PathwayStep)
            .join(PathwayStep, JourneyStep.pathway_step_id == PathwayStep.id)
            .filter(JourneyStep.id == uuid_value(args["step_id"], "step_id"))
            .first()
        )
        if not row or (journey is not None and row[0].journey_id != journey.id):
            raise ToolValidationError("That step does not belong to this journey")
        step, template = row
        if spec.name == "complete_step":
            if step.status not in ("READY", "IN_PROGRESS"):
                raise ToolValidationError(
                    f"Only ready or in-progress steps can be completed; this step is {(step.status or '').lower()}."
                )
            from app.api.v1.journeys import _check_step_completion_permission

            try:
                _check_step_completion_permission(db, journey, step, template, user)
            except HTTPException as exc:
                raise _http_to_tool(exc)
        elif spec.name == "submit_step_update":
            if (step.owner_role or template.owner_role) != "PATIENT":
                raise ToolPermissionError("This task is not assigned to you")
            if step.status not in ("READY", "IN_PROGRESS"):
                raise ToolValidationError("This task is not currently open for an update")
        elif spec.name == "update_step_time_limit" and step.status in ("COMPLETED", "CANCELLED"):
            raise ToolValidationError("Time limits cannot be changed for completed or cancelled steps")

    if spec.name == "start_pathway":
        pathway = db.query(Pathway).filter(
            Pathway.id == uuid_value(args["pathway_id"], "pathway_id"), Pathway.status == "ACTIVE"
        ).first()
        if not pathway:
            raise ToolValidationError("That is not an active care pathway")
        if find_active_journey(db, uuid_value(args["patient_id"], "patient_id"), pathway.id):
            raise ToolValidationError("This patient already has an active journey for this pathway")
    elif spec.name == "submit_event":
        args["event_type"] = enum_value(args["event_type"], write.event_types_for(user), "event_type")
    elif spec.name == "update_exception":
        if not db.query(ExceptionRecord).filter(ExceptionRecord.id == uuid_value(args["exception_id"], "exception_id")).first():
            raise ToolValidationError("Exception not found")
    elif spec.name in ("set_user_role", "set_user_status"):
        write._target_user(db, user, args["user_id"])
    elif spec.name == "create_pathway":
        payload = write.build_pathway_payload(args)
        args["code"] = payload.code
        if db.query(Pathway).filter(Pathway.code == payload.code).first():
            raise ToolValidationError("A pathway with this code already exists")


def prepare_arguments(db: Session, user, spec: ToolSpec, args: dict[str, Any]) -> dict[str, Any]:
    """Normalize + validate LLM arguments. Raises ToolValidationError /
    ToolPermissionError / HTTPException. Never writes."""
    if not isinstance(args, dict):
        raise ToolValidationError("Tool arguments must be a JSON object")
    clean = _normalize(spec, args)
    if spec.confirm:
        try:
            _check_targets(db, user, spec, clean)
        except HTTPException as exc:
            raise _http_to_tool(exc)
    return clean


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------

def describe_action(db: Session, user, name: str, args: dict[str, Any]) -> dict[str, Any]:
    return write.describe_action(db, user, name, args)


def execute_tool(db: Session, user, name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Validate role, then run the tool with the user's own authorization."""
    spec = TOOL_SPECS.get(name)
    if spec is None:
        raise ToolValidationError(f"Unknown tool: {name}")
    if not is_allowed(user, spec):
        raise ToolPermissionError("")
    return spec.executor(db, user, args)
