"""
Read-only chatbot tools. Each one is a thin function over a DB query, always
scoped by the requesting user's role (scope_patient_ids / ownership checks).
They run immediately — no confirmation needed because nothing changes.
"""
from typing import Any

from sqlalchemy.orm import Session

from app.core.authorization import STAFF_ROLES, get_journey_scoped, scope_patient_ids
from app.llm.tool_helpers import (
    ToolPermissionError,
    ToolValidationError,
    enum_value,
    int_value,
    iso,
    patient_by_id,
    patient_name,
    patient_ref,
    pathway_name_map,
    readable_journey,
    require_dict,
    serialize_journey,
    serialize_step,
    staff_required,
    target_patient_id,
    text_value,
    uuid_value,
)
from app.models import (
    ChatAuditLog,
    ExceptionRecord,
    Journey,
    JourneyStep,
    Patient,
    PatientEvent,
    Pathway,
    PathwayStep,
    User,
)
from app.services.journey_service import pathway_steps

JOURNEY_STATUSES = ("ACTIVE", "BLOCKED", "COMPLETED", "CANCELLED")
PRIORITIES = ("CRITICAL", "HIGH", "MEDIUM", "LOW")
EXCEPTION_STATUSES = ("OPEN", "IN_PROGRESS", "RESOLVED", "DISMISSED")


def _result(tool: str, summary: str, data: dict[str, Any]) -> dict[str, Any]:
    return {"tool": tool, "summary": summary, "data": data}


def _journeys_in_scope(
    db: Session, user, patient_id=None, status: str | None = None, priority: str | None = None,
) -> list[Journey]:
    q = db.query(Journey)
    if patient_id is not None:
        q = q.filter(Journey.patient_id == patient_id)
    else:
        ids = scope_patient_ids(db, user)
        if ids is not None:
            q = q.filter(Journey.patient_id.in_(ids))
    if status:
        q = q.filter(Journey.status == status)
    if priority:
        q = q.filter(Journey.priority == priority)
    return q.order_by(Journey.updated_at.desc()).limit(25).all()


def _serialize_many(db: Session, journeys: list[Journey]) -> list[dict[str, Any]]:
    names = pathway_name_map(db, {j.pathway_id for j in journeys})
    patients = {
        p.id: p for p in db.query(Patient).filter(Patient.id.in_({j.patient_id for j in journeys})).all()
    } if journeys else {}
    return [serialize_journey(j, patients.get(j.patient_id), names.get(j.pathway_id)) for j in journeys]


# ---------------------------------------------------------------------------
# Patients
# ---------------------------------------------------------------------------

def tool_search_patients(db: Session, user, args: dict[str, Any]) -> dict[str, Any]:
    """Resolve names like 'Vansh' to patient ids."""
    args = require_dict(args)
    staff_required(user)
    query = text_value(args.get("query"), "query", max_len=120)
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
    return _result(
        "search_patients",
        f"Found {len(matches)} patient(s) matching \"{query}\"." if matches else f"No patients match \"{query}\".",
        {"patients": [patient_ref(p) for p in matches]},
    )


def tool_list_patients(db: Session, user, args: dict[str, Any]) -> dict[str, Any]:
    args = require_dict(args)
    staff_required(user)
    limit = int_value(args.get("limit", 20), "limit", 1, 50)
    q = db.query(Patient)
    ids = scope_patient_ids(db, user)
    if ids is not None:
        q = q.filter(Patient.id.in_(ids))
    total = q.order_by(None).count()
    rows = q.order_by(Patient.created_at.desc()).limit(limit).all()
    return _result(
        "list_patients",
        f"Showing {len(rows)} of {total} patient(s).",
        {"patients": [patient_ref(p) for p in rows], "total": total},
    )


def tool_get_patient_summary(db: Session, user, args: dict[str, Any]) -> dict[str, Any]:
    """Patient identity + their journeys. Patients can only ever get their own."""
    args = require_dict(args)
    patient_id = target_patient_id(db, user, args)
    patient = patient_by_id(db, patient_id)
    if not patient:
        raise ToolValidationError("Patient not found")

    journeys = _journeys_in_scope(db, user, patient_id=patient_id)
    summary = {"id": str(patient.id), "name": patient_name(patient), "reference": patient.patient_reference}
    if user.role in STAFF_ROLES:
        summary["date_of_birth"] = iso(patient.date_of_birth)
        summary["gender"] = patient.gender
        summary["email"] = patient.email
    return _result(
        "get_patient_summary",
        f"Patient {summary['name']} ({summary['reference']}) has {len(journeys)} journey(s).",
        {"patient": summary, "journeys": _serialize_many(db, journeys)},
    )


# ---------------------------------------------------------------------------
# Pathways & journeys
# ---------------------------------------------------------------------------

def tool_list_pathways(db: Session, user, args: dict[str, Any]) -> dict[str, Any]:
    args = require_dict(args)
    staff_required(user)
    pathways = db.query(Pathway).filter(Pathway.status == "ACTIVE").order_by(Pathway.name).all()
    data = []
    for pathway in pathways:
        templates = pathway_steps(db, pathway.id)
        data.append({
            "id": str(pathway.id),
            "code": pathway.code,
            "name": pathway.name,
            "description": pathway.description,
            "version": pathway.version,
            "steps": [t.name for t in templates],
        })
    return _result("list_pathways", f"{len(data)} active pathway(s) available.", {"pathways": data})


def tool_list_journeys(db: Session, user, args: dict[str, Any]) -> dict[str, Any]:
    args = require_dict(args)
    status = enum_value(args["status"], JOURNEY_STATUSES, "status") if args.get("status") else None
    priority = enum_value(args["priority"], PRIORITIES, "priority") if args.get("priority") else None
    patient_id = None
    if args.get("patient_id") and user.role != "PATIENT":
        patient_id = target_patient_id(db, user, args)
    journeys = _journeys_in_scope(db, user, patient_id, status, priority)
    return _result("list_journeys", f"Found {len(journeys)} journeys.", {"journeys": _serialize_many(db, journeys)})


def tool_get_journey_steps(db: Session, user, args: dict[str, Any]) -> dict[str, Any]:
    args = require_dict(args)
    journey = get_journey_scoped(uuid_value(args.get("journey_id"), "journey_id"), db, user)
    rows = (
        db.query(JourneyStep, PathwayStep)
        .join(PathwayStep, JourneyStep.pathway_step_id == PathwayStep.id)
        .filter(JourneyStep.journey_id == journey.id)
        .order_by(PathwayStep.sequence_number)
        .limit(100)
        .all()
    )
    pathway = db.query(Pathway).filter(Pathway.id == journey.pathway_id).first()
    return _result(
        "get_journey_steps",
        f"Journey {str(journey.id)[:8]} has {len(rows)} steps.",
        {
            "journey": serialize_journey(journey, patient_by_id(db, journey.patient_id), pathway.name if pathway else None),
            "steps": [serialize_step(step, template) for step, template in rows],
        },
    )


def tool_get_journey_events(db: Session, user, args: dict[str, Any]) -> dict[str, Any]:
    args = require_dict(args)
    journey = readable_journey(db, user, uuid_value(args.get("journey_id"), "journey_id"))
    limit = int_value(args.get("limit", 15), "limit", 1, 50)
    events = (
        db.query(PatientEvent)
        .filter(PatientEvent.journey_id == journey.id)
        .order_by(PatientEvent.event_time.desc())
        .limit(limit)
        .all()
    )
    return _result(
        "get_journey_events",
        f"{len(events)} recent event(s) on journey {str(journey.id)[:8]}.",
        {
            "journey_id": str(journey.id),
            "events": [
                {
                    "id": str(e.id),
                    "event_type": e.event_type,
                    "source": e.source,
                    "event_time": iso(e.event_time),
                    "comment": (e.payload or {}).get("comment"),
                    "processed": e.processed,
                }
                for e in events
            ],
        },
    )


def tool_get_pending_tasks(db: Session, user, args: dict[str, Any]) -> dict[str, Any]:
    """Open (pending/ready/in-progress/blocked) steps across the user's scope."""
    args = require_dict(args)
    patient_id = target_patient_id(db, user, args) if (user.role == "PATIENT" or args.get("patient_id")) else None

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

    names = pathway_name_map(db, {journey.pathway_id for _, _, journey in rows})
    patient_ids = {journey.patient_id for _, _, journey in rows}
    patient_names = {
        p.id: patient_name(p) for p in db.query(Patient).filter(Patient.id.in_(patient_ids)).all()
    } if patient_ids else {}

    by_journey: dict[str, dict[str, Any]] = {}
    for step, template, journey in rows:
        entry = by_journey.setdefault(str(journey.id), {
            "journey_id": str(journey.id),
            "patient_name": patient_names.get(journey.patient_id),
            "pathway_name": names.get(journey.pathway_id),
            "tasks": [],
        })
        entry["tasks"].append(serialize_step(step, template))
    total = sum(len(e["tasks"]) for e in by_journey.values())
    return _result(
        "get_pending_tasks",
        f"{total} open task(s) across {len(by_journey)} journey(s).",
        {"journeys": list(by_journey.values())},
    )


# ---------------------------------------------------------------------------
# Staff / admin views (same query code as the REST endpoints)
# ---------------------------------------------------------------------------

def tool_get_dashboard_summary(db: Session, user, args: dict[str, Any]) -> dict[str, Any]:
    from app.api.v1.dashboard import dashboard

    require_dict(args)
    staff_required(user)
    summary = dashboard(db=db, user=user)
    recent = summary.pop("recent_journeys", [])
    return _result(
        "get_dashboard_summary",
        (f"{summary['active_journeys']} active, {summary['blocked_journeys']} blocked, "
         f"{summary['open_exceptions']} open exception(s), {summary['pending_steps']} pending step(s)."),
        {"metrics": summary, "recent_journey_count": len(recent)},
    )


def tool_list_exceptions(db: Session, user, args: dict[str, Any]) -> dict[str, Any]:
    args = require_dict(args)
    staff_required(user)
    status = enum_value(args["status"], EXCEPTION_STATUSES, "status") if args.get("status") else None
    severity = enum_value(args["severity"], PRIORITIES, "severity") if args.get("severity") else None
    q = db.query(ExceptionRecord).join(Journey, Journey.id == ExceptionRecord.journey_id)
    ids = scope_patient_ids(db, user)
    if ids is not None:
        q = q.filter(Journey.patient_id.in_(ids))
    if status:
        q = q.filter(ExceptionRecord.status == status)
    if severity:
        q = q.filter(ExceptionRecord.severity == severity)
    rows = q.order_by(ExceptionRecord.created_at.desc()).limit(20).all()
    return _result(
        "list_exceptions",
        f"Found {len(rows)} exception(s).",
        {"exceptions": [
            {
                "id": str(e.id),
                "journey_id": str(e.journey_id),
                "severity": (e.severity or "").lower(),
                "status": (e.status or "").lower(),
                "type": e.exception_type,
                "title": e.title,
                "description": e.description,
                "recommended_action": e.recommended_action,
                "created_at": iso(e.created_at),
            }
            for e in rows
        ]},
    )


def tool_list_users(db: Session, user, args: dict[str, Any]) -> dict[str, Any]:
    args = require_dict(args)
    if user.role != "ADMIN":
        raise ToolPermissionError("Only administrators can view user accounts")
    q = db.query(User)
    if args.get("role"):
        q = q.filter(User.role == enum_value(args["role"], ("ADMIN", "CLINICIAN", "CARE_COORDINATOR", "PATIENT"), "role"))
    if args.get("search"):
        term = f"%{text_value(args['search'], 'search', max_len=120)}%"
        q = q.filter(User.email.ilike(term) | User.display_name.ilike(term))
    rows = q.order_by(User.created_at.desc()).limit(25).all()
    return _result(
        "list_users",
        f"Found {len(rows)} user(s).",
        {"users": [
            {
                "id": str(u.id),
                "display_name": u.display_name,
                "email": u.email,
                "role": u.role,
                "is_active": u.is_active,
            }
            for u in rows
        ]},
    )


def tool_get_chat_audit(db: Session, user, args: dict[str, Any]) -> dict[str, Any]:
    args = require_dict(args)
    if user.role != "ADMIN":
        raise ToolPermissionError("Only administrators can view the chatbot audit trail")
    limit = int_value(args.get("limit", 10), "limit", 1, 25)
    rows = db.query(ChatAuditLog).order_by(ChatAuditLog.created_at.desc()).limit(limit).all()
    return _result(
        "get_chat_audit",
        f"Last {len(rows)} chatbot audit entries.",
        {"entries": [
            {
                "tool": r.tool_name,
                "event": r.event,
                "permission_result": r.permission_result,
                "user_id": str(r.user_id),
                "detail": r.detail,
                "created_at": iso(r.created_at),
            }
            for r in rows
        ]},
    )
