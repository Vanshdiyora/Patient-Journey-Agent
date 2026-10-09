"""
State-changing chatbot tools. They only ever run after the user confirms the
proposal in chat, and re-check role + scope at execution time.

Wherever a REST endpoint already implements the action, the executor calls that
handler function directly so the chatbot cannot drift from the API's rules
(step-owner checks, patient event allowlist, user-management guards, ...).
Handlers are imported lazily to avoid an import cycle with app.api.
"""
from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.authorization import STAFF_ROLES, get_journey_for_action
from app.llm.tool_helpers import (
    ToolPermissionError,
    ToolValidationError,
    bool_value,
    enum_value,
    int_value,
    patient_by_id,
    patient_in_scope,
    patient_name,
    require_dict,
    serialize_journey,
    staff_required,
    text_value,
    uuid_value,
)
from app.models import ExceptionRecord, Journey, JourneyStep, Pathway, PathwayStep, User
from app.services.journey_service import pathway_steps, start_journey_for_patient

PRIORITIES = ("CRITICAL", "HIGH", "MEDIUM", "LOW")
ROLES = ("ADMIN", "CLINICIAN", "CARE_COORDINATOR", "PATIENT")
EXCEPTION_STATUSES = ("OPEN", "IN_PROGRESS", "RESOLVED", "DISMISSED")

# Event types per role. Patients get exactly what POST /me/journeys/{id}/events allows.
PATIENT_EVENT_TYPES = (
    "SYMPTOM_REPORTED", "APPOINTMENT_PREFERENCE", "DOCUMENT_UPLOADED", "GENERAL_UPDATE", "QUESTION_ASKED",
)
STAFF_EVENT_TYPES = PATIENT_EVENT_TYPES + (
    "MEDICATION_TAKEN", "VITALS_RECORDED", "ATTENDANCE_CONFIRMED", "TASK_COMPLETED", "STATUS_REPORT",
)


def event_types_for(user) -> tuple[str, ...]:
    return PATIENT_EVENT_TYPES if user.role == "PATIENT" else STAFF_EVENT_TYPES


def _result(tool: str, summary: str, data: dict[str, Any]) -> dict[str, Any]:
    return {"tool": tool, "summary": summary, "data": data}


def _validated(model, **kwargs):
    """Build a REST request model; surface field errors as a fixable message."""
    try:
        return model(**kwargs)
    except ValidationError as exc:
        first = exc.errors()[0]
        loc = ".".join(str(p) for p in first.get("loc", ()))
        raise ToolValidationError(f"{loc + ': ' if loc else ''}{first.get('msg', 'invalid value')}")


# ---------------------------------------------------------------------------
# Journeys
# ---------------------------------------------------------------------------

def tool_start_pathway(db: Session, user, args: dict[str, Any]) -> dict[str, Any]:
    """Same service function as POST /patients/{id}/journeys."""
    args = require_dict(args)
    staff_required(user)
    patient_id = uuid_value(args.get("patient_id"), "patient_id")
    pathway_id = uuid_value(args.get("pathway_id"), "pathway_id")
    priority = enum_value(args.get("priority") or "MEDIUM", PRIORITIES, "priority")

    patient = patient_in_scope(db, user, patient_id)
    journey = start_journey_for_patient(db, patient_id, pathway_id, priority)
    db.commit()
    db.refresh(journey)

    pathway = db.query(Pathway).filter(Pathway.id == pathway_id).first()
    return _result(
        "start_pathway",
        f"{pathway.name if pathway else 'Pathway'} started successfully for {patient_name(patient)}.",
        {
            "journey": serialize_journey(journey, patient, pathway.name if pathway else None),
            "next_steps": [t.name for t in pathway_steps(db, pathway_id)[:3]],
        },
    )


def tool_orchestrate_journey(db: Session, user, args: dict[str, Any]) -> dict[str, Any]:
    args = require_dict(args)
    journey = get_journey_for_action(uuid_value(args.get("journey_id"), "journey_id"), db, user)
    from app.orchestration.journey_engine import JourneyEngine

    result = JourneyEngine(db).evaluate(journey.id)
    if not result:
        raise ToolValidationError("Journey not found")
    db.commit()
    db.refresh(result["journey"])
    return _result(
        "orchestrate_journey",
        f"Re-evaluated journey {str(journey.id)[:8]}.",
        {
            "journey_id": str(journey.id),
            "status": (result["journey"].status or "").lower(),
            "steps_updated": len(result.get("steps", [])),
        },
    )


def tool_submit_event(db: Session, user, args: dict[str, Any]) -> dict[str, Any]:
    """Patients use the patient-portal handler; staff use the staff events handler."""
    args = require_dict(args)
    journey_id = uuid_value(args.get("journey_id"), "journey_id")
    event_type = enum_value(args.get("event_type"), event_types_for(user), "event_type")
    comment = text_value(args.get("comment"), "comment", max_len=2000)

    if user.role == "PATIENT":
        from app.api.v1.me import submit_patient_event
        from app.schemas.patient_event import PatientEventCreate

        data = _validated(PatientEventCreate, event_type=event_type, payload={"comment": comment})
        event = submit_patient_event(journey_id=journey_id, data=data, user=user, db=db)
    elif user.role in STAFF_ROLES:
        from app.api.v1.events import add_event
        from app.schemas import EventCreate

        data = _validated(
            EventCreate, event_type=event_type, source="carepath-ui",
            event_time=datetime.now(timezone.utc), payload={"comment": comment},
        )
        event = add_event(journey_id=journey_id, data=data, db=db, user=user)
    else:
        raise ToolPermissionError("Your role cannot record updates")
    return _result(
        "submit_event",
        f"Recorded a {event_type.replace('_', ' ').lower()} update on journey {str(journey_id)[:8]}.",
        {"event_id": str(event.id), "event_type": event.event_type, "source": event.source, "journey_id": str(journey_id)},
    )


def tool_complete_step(db: Session, user, args: dict[str, Any]) -> dict[str, Any]:
    from app.api.v1.journeys import complete_journey_step
    from app.schemas.journey import JourneyStepComplete

    args = require_dict(args)
    staff_required(user)
    out = complete_journey_step(
        journey_id=uuid_value(args.get("journey_id"), "journey_id"),
        step_id=uuid_value(args.get("step_id"), "step_id"),
        data=JourneyStepComplete(confirmed=True),
        db=db, user=user,
    )
    return _result(
        "complete_step",
        "Step marked as completed and the journey was re-evaluated.",
        {"journey_id": out["journey_id"], "step_id": out["step_id"], "status": str(out["status"]).lower()},
    )


def tool_submit_step_update(db: Session, user, args: dict[str, Any]) -> dict[str, Any]:
    """Patient reports a task of theirs as done; staff then review it."""
    from app.api.v1.me import submit_patient_step
    from app.schemas.patient_event import PatientStepSubmission

    args = require_dict(args)
    if user.role != "PATIENT":
        raise ToolPermissionError("Only patients can submit their own task updates")
    event = submit_patient_step(
        journey_id=uuid_value(args.get("journey_id"), "journey_id"),
        step_id=uuid_value(args.get("step_id"), "step_id"),
        data=_validated(PatientStepSubmission, comment=args.get("comment")),
        user=user, db=db,
    )
    return _result(
        "submit_step_update",
        "Your update was sent to your care team for review.",
        {"event_id": str(event.id), "journey_id": str(args["journey_id"]), "step_id": str(args["step_id"])},
    )


def tool_update_step_time_limit(db: Session, user, args: dict[str, Any]) -> dict[str, Any]:
    from app.api.v1.journeys import update_step_time_limit
    from app.schemas.journey import JourneyStepTimeLimitUpdate

    args = require_dict(args)
    staff_required(user)
    hours = int_value(args.get("time_limit_hours"), "time_limit_hours", 1, 8760)
    journey_id = uuid_value(args.get("journey_id"), "journey_id")
    step_id = uuid_value(args.get("step_id"), "step_id")
    update_step_time_limit(
        journey_id=journey_id, step_id=step_id,
        data=JourneyStepTimeLimitUpdate(time_limit_hours=hours), db=db, user=user,
    )
    return _result(
        "update_step_time_limit",
        f"Time limit set to {hours} hour(s).",
        {"journey_id": str(journey_id), "step_id": str(step_id), "time_limit_hours": hours},
    )


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

def tool_update_exception(db: Session, user, args: dict[str, Any]) -> dict[str, Any]:
    from app.api.v1.exceptions import update_exception
    from app.schemas import ExceptionUpdate

    args = require_dict(args)
    staff_required(user)
    status = enum_value(args.get("status"), EXCEPTION_STATUSES, "status")
    note = args.get("recommended_action")
    item = update_exception(
        exception_id=uuid_value(args.get("exception_id"), "exception_id"),
        data=ExceptionUpdate(status=status, recommended_action=note.strip() if isinstance(note, str) and note.strip() else None),
        db=db, user=user,
    )
    return _result(
        "update_exception",
        f"Exception \"{item.title}\" is now {status.replace('_', ' ').lower()}.",
        {"exception_id": str(item.id), "status": status.lower()},
    )


# ---------------------------------------------------------------------------
# Administration
# ---------------------------------------------------------------------------

def _admin_required(user) -> None:
    if user.role != "ADMIN":
        raise ToolPermissionError("Only administrators can do this")


def _target_user(db: Session, admin, raw_id: Any) -> User:
    target = db.query(User).filter(User.id == uuid_value(raw_id, "user_id")).first()
    if not target:
        raise ToolValidationError("User not found")
    if target.id == admin.id:
        raise ToolValidationError("For safety you cannot change your own role or status from chat")
    return target


def tool_set_user_role(db: Session, user, args: dict[str, Any]) -> dict[str, Any]:
    from app.api.v1.admin import RoleUpdate, set_user_role

    args = require_dict(args)
    _admin_required(user)
    target = _target_user(db, user, args.get("user_id"))
    role = enum_value(args.get("role"), ROLES, "role")
    set_user_role(user_id=target.id, data=RoleUpdate(role=role), db=db, _admin=user)
    return _result(
        "set_user_role",
        f"{target.display_name} is now {role.replace('_', ' ').title()}.",
        {"user_id": str(target.id), "role": role},
    )


def tool_set_user_status(db: Session, user, args: dict[str, Any]) -> dict[str, Any]:
    from app.api.v1.admin import StatusUpdate, set_user_status

    args = require_dict(args)
    _admin_required(user)
    target = _target_user(db, user, args.get("user_id"))
    active = bool_value(args.get("is_active"), "is_active")
    set_user_status(user_id=target.id, data=StatusUpdate(is_active=active), db=db, _admin=user)
    return _result(
        "set_user_status",
        f"{target.display_name}'s account is now {'active' if active else 'deactivated'}.",
        {"user_id": str(target.id), "is_active": active},
    )


def build_pathway_payload(args: dict[str, Any]):
    """Validate a create_pathway request into the REST model (no writes)."""
    from app.schemas.pathway import PathwayCreate

    steps = args.get("steps")
    if not isinstance(steps, list) or not steps:
        raise ToolValidationError("steps must be a non-empty list")
    return _validated(
        PathwayCreate,
        code=args.get("code"), name=args.get("name"), description=args.get("description"),
        steps=[
            {
                "code": s.get("code") or str(s.get("name", "")).upper().replace(" ", "_"),
                "name": s.get("name"),
                "description": s.get("description"),
                "step_type": s.get("step_type") or "TASK",
                "owner_role": s.get("owner_role") or "CARE_COORDINATOR",
                "time_limit_hours": s.get("time_limit_hours"),
            }
            for s in steps if isinstance(s, dict)
        ],
    )


def tool_create_pathway(db: Session, user, args: dict[str, Any]) -> dict[str, Any]:
    from app.api.v1.pathways import create_pathway

    args = require_dict(args)
    _admin_required(user)
    created = create_pathway(data=build_pathway_payload(args), db=db, _admin=user)
    return _result(
        "create_pathway",
        f"Pathway \"{created['name']}\" created with {len(created.get('steps', []))} step(s).",
        {"pathway_id": str(created["id"]), "name": created["name"]},
    )


# ---------------------------------------------------------------------------
# Confirmation cards
# ---------------------------------------------------------------------------

def _journey_context(db: Session, args: dict[str, Any]) -> tuple[str | None, str | None]:
    try:
        journey = db.query(Journey).filter(Journey.id == uuid_value(args.get("journey_id"), "journey_id")).first()
        if not journey:
            return None, None
        pathway = db.query(Pathway).filter(Pathway.id == journey.pathway_id).first()
        return patient_name(patient_by_id(db, journey.patient_id)), pathway.name if pathway else None
    except Exception:  # noqa: BLE001 — cosmetic only
        return None, None


def _step_name(db: Session, args: dict[str, Any]) -> str | None:
    try:
        row = (
            db.query(PathwayStep.name)
            .join(JourneyStep, JourneyStep.pathway_step_id == PathwayStep.id)
            .filter(JourneyStep.id == uuid_value(args.get("step_id"), "step_id"))
            .first()
        )
        return row[0] if row else None
    except Exception:  # noqa: BLE001
        return None


def describe_action(db: Session, user, name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Human-readable confirmation-card data. Best-effort; never blocks the action."""
    description: dict[str, Any] = {"title": name.replace("_", " ").capitalize(), "changes": []}
    try:
        if name == "start_pathway":
            pathway = db.query(Pathway).filter(Pathway.id == uuid_value(args.get("pathway_id"), "p")).first()
            patient = patient_by_id(db, uuid_value(args.get("patient_id"), "p"))
            n_steps = len(pathway_steps(db, pathway.id)) if pathway else 0
            description.update({
                "title": f"Start {pathway.name}" if pathway else "Start pathway",
                "patient": patient_name(patient),
                "patient_reference": patient.patient_reference if patient else None,
                "pathway": pathway.name if pathway else None,
                "priority": args.get("priority") or "MEDIUM",
                "changes": [
                    "Create the journey",
                    f"Initialize {n_steps} pathway stage{'s' if n_steps != 1 else ''}",
                    "Create the initial pending tasks",
                    "Set the journey status to Active",
                ],
            })
        elif name == "submit_event":
            patient, _ = _journey_context(db, args)
            event_type = str(args.get("event_type") or "").replace("_", " ").lower()
            changes = [f"Record a {event_type or 'general'} update on the journey"]
            if args.get("comment"):
                changes.append(f"Attach note: \"{str(args['comment'])[:160]}\"")
            description.update({"title": "Record an update", "patient": patient, "changes": changes})
        elif name == "orchestrate_journey":
            patient, pathway = _journey_context(db, args)
            description.update({
                "title": "Run journey orchestration", "patient": patient,
                "changes": [
                    "Re-run the deterministic journey rules",
                    "Refresh step statuses, due dates and blockers",
                ],
            })
        elif name == "complete_step":
            patient, pathway = _journey_context(db, args)
            step = _step_name(db, args)
            description.update({
                "title": f"Complete step: {step}" if step else "Complete step", "patient": patient,
                "changes": [
                    "Confirm the care task was actually performed",
                    f"Mark \"{step or 'the step'}\" as completed" + (f" on {pathway}" if pathway else ""),
                    "Record your confirmation in the journey history",
                    "Re-evaluate the journey and unlock follow-up steps",
                ],
            })
        elif name == "submit_step_update":
            step = _step_name(db, args)
            description.update({
                "title": f"Report task: {step}" if step else "Report task update",
                "changes": [
                    f"Tell your care team you finished \"{step or 'this task'}\"",
                    f"Attach note: \"{str(args.get('comment', ''))[:160]}\"",
                    "Staff review it before the step is marked complete",
                ],
            })
        elif name == "update_step_time_limit":
            patient, _ = _journey_context(db, args)
            step = _step_name(db, args)
            description.update({
                "title": "Change step time limit", "patient": patient,
                "changes": [f"Set \"{step or 'the step'}\" time limit to {args.get('time_limit_hours')} hours",
                            "Recalculate its due date and re-evaluate the journey"],
            })
        elif name == "update_exception":
            item = db.query(ExceptionRecord).filter(ExceptionRecord.id == uuid_value(args.get("exception_id"), "e")).first()
            status = str(args.get("status") or "").replace("_", " ").lower()
            changes = [f"Set the exception to {status}"]
            if args.get("recommended_action"):
                changes.append(f"Record action: \"{str(args['recommended_action'])[:160]}\"")
            description.update({"title": f"Update exception: {item.title}" if item else "Update exception", "changes": changes})
        elif name in ("set_user_role", "set_user_status"):
            target = db.query(User).filter(User.id == uuid_value(args.get("user_id"), "u")).first()
            who = f"{target.display_name} ({target.email})" if target else "the user"
            if name == "set_user_role":
                change = f"Change {who} from {target.role if target else '?'} to {str(args.get('role')).upper()}"
                title = "Change user role"
            else:
                active = bool_value(args.get("is_active"), "is_active")
                change = f"{'Reactivate' if active else 'Deactivate'} the account of {who}"
                title = "Change account status"
            description.update({"title": title, "changes": [change, "Takes effect immediately"]})
        elif name == "create_pathway":
            steps = args.get("steps") or []
            description.update({
                "title": f"Create pathway: {args.get('name')}",
                "changes": [f"Create pathway \"{args.get('name')}\" ({str(args.get('code') or '').upper()})"]
                + [f"Step {i}: {s.get('name')}" for i, s in enumerate(steps[:8], 1) if isinstance(s, dict)],
            })
    except Exception:  # noqa: BLE001 — description is cosmetic only
        pass
    return description
