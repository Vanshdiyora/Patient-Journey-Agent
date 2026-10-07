"""
Chat assistant service layer.

Owns conversation persistence, the LLM tool-calling loop, and the two-step
"propose -> confirm -> execute" flow for mutating tools. All tool execution is
delegated to app.llm.tools which re-checks the user's authorization at
execution time — the LLM is never trusted for permission decisions.

Every state-changing event (action proposed / confirmed / executed / failed /
rejected / expired) is written to chat_audit_log.
"""
import json
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.authorization import scope_note
from app.llm import tools as chat_tools
from app.llm.provider import get_llm_client
from app.models import ChatAuditLog, ChatMessage, ChatSession, User

MAX_HISTORY_MESSAGES = 20
# A proposed action must be confirmed within this window or it expires.
PENDING_ACTION_TTL_MINUTES = 15

# Pending-action lifecycle statuses (stored in message meta).
PENDING = "pending"
EXECUTED = "executed"
FAILED = "failed"
REJECTED = "rejected"
EXPIRED = "expired"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _system_prompt(user: User) -> str:
    """Role-aware instructions. The role/scope are stated for tone only —
    real authorization always happens server-side in the tool executors."""
    return (
        "You are CarePath Assistant, an in-app copilot for a patient-journey orchestrator. "
        "You help staff and patients inspect journeys and record updates.\n"
        f"The signed-in user's role is {user.role}; their data scope is: {scope_note(user)}.\n"
        "Rules:\n"
        "- Answer in the user's language, briefly and helpfully.\n"
        "- You may call tools to look up data or to propose updates. Authorization is "
        "enforced server-side regardless of what you say or ask for.\n"
        "- To talk about a patient by name, resolve them first with search_patients. If "
        "several patients match, list the matches and ask the user to pick one — never "
        "guess a patient id. If none match, say so.\n"
        "- To start a pathway you need patient_id and pathway_id: resolve the patient "
        "with search_patients and the pathway with list_pathways. If the requested "
        "pathway is ambiguous, ask which one.\n"
        "- Mutating tools (start_pathway, submit_event, orchestrate_journey) REQUIRE "
        "explicit user confirmation. Summarize what will change in plain language; the "
        "app collects confirmation via the UI. Never claim a change is done unless a "
        "tool result says so.\n"
        "- If a journey id is missing, call list_journeys or get_patient_summary first, "
        "or ask a short clarifying question.\n"
        "- Never invent journey ids, patient data, or medical advice. If the user asks "
        "for something no tool supports, say you can't help with that."
    )


def audit(
    db: Session,
    *,
    user: User,
    session: ChatSession | None = None,
    message: ChatMessage | None = None,
    tool_name: str,
    event: str,
    target_entity: str | None = None,
    target_entity_id: Any = None,
    parameters: dict[str, Any] | None = None,
    permission_result: str = "allowed",
    detail: str | None = None,
) -> None:
    """Write one chatbot audit row. Failures must not break the chat flow."""
    try:
        db.add(ChatAuditLog(
            user_id=user.id,
            conversation_id=session.id if session else None,
            message_id=message.id if message else None,
            tool_name=(tool_name or "")[:100],
            event=event,
            target_entity=(target_entity or "")[:100] or None,
            target_entity_id=str(target_entity_id)[:64] if target_entity_id is not None else None,
            parameters=parameters,
            permission_result=permission_result,
            detail=(detail[:2000] if detail else None),
            created_at=_utcnow(),
        ))
    except Exception:  # noqa: BLE001 — audit is best-effort, never fatal
        db.rollback()


def get_session_for_user(db: Session, user: User, session_id: UUID) -> ChatSession:
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id, ChatSession.user_id == user.id
    ).first()
    if not session:
        raise HTTPException(404, "Chat session not found")
    return session


def create_session(db: Session, user: User, title: str | None = None) -> ChatSession:
    session = ChatSession(user_id=user.id, title=(title or "New conversation")[:200])
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def list_sessions(db: Session, user: User) -> list[ChatSession]:
    return (
        db.query(ChatSession)
        .filter(ChatSession.user_id == user.id, ChatSession.is_archived.is_(False))
        .order_by(ChatSession.updated_at.desc())
        .limit(50)
        .all()
    )


def rename_session(db: Session, user: User, session_id: UUID, title: str) -> ChatSession:
    session = get_session_for_user(db, user, session_id)
    session.title = (title or "").strip()[:200] or session.title
    session.updated_at = _utcnow()
    db.commit()
    db.refresh(session)
    return session


def archive_session(db: Session, user: User, session_id: UUID) -> ChatSession:
    session = get_session_for_user(db, user, session_id)
    session.is_archived = True
    session.updated_at = _utcnow()
    db.commit()
    db.refresh(session)
    return session


def get_messages(db: Session, user: User, session_id: UUID, limit: int = 200) -> list[ChatMessage]:
    session = get_session_for_user(db, user, session_id)
    return (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session.id)
        .order_by(ChatMessage.created_at.asc())
        .limit(limit)
        .all()
    )


def _add_message(db: Session, session: ChatSession, role: str, content: str,
                 meta: dict[str, Any] | None = None) -> ChatMessage:
    msg = ChatMessage(session_id=session.id, role=role, content=content, meta=meta)
    db.add(msg)
    session.updated_at = _utcnow()
    db.flush()
    return msg


def _title_from_message(text: str) -> str:
    text = text.strip().replace("\n", " ")
    return (text[:60] + "…") if len(text) > 60 else (text or "New conversation")


def _history_for_llm(db: Session, session: ChatSession) -> list[dict[str, str]]:
    rows = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session.id)
        .order_by(ChatMessage.created_at.desc())
        .limit(MAX_HISTORY_MESSAGES)
        .all()
    )
    rows.reverse()
    return [
        {"role": m.role, "content": m.content}
        for m in rows
        if m.role in ("user", "assistant")
    ]


def _pending_expires_at() -> str:
    return (_utcnow() + timedelta(minutes=PENDING_ACTION_TTL_MINUTES)).isoformat()


def _pending_is_expired(pending: dict[str, Any]) -> bool:
    """Actions without a parseable expires_at are treated as expired (defensive)."""
    raw = pending.get("expires_at")
    if not raw:
        return True
    try:
        expires_at = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return True
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return _utcnow() > expires_at


def process_user_message(
    db: Session,
    user: User,
    session_id: UUID,
    content: str,
    llm_client: Any | None = None,
) -> dict[str, Any]:
    """
    Persist the user's message, run the LLM tool loop, persist the assistant
    turn. Mutating tool calls become a stored `pending_action` that the user
    must confirm in chat before anything executes. `llm_client` is injectable
    for tests; production always uses the configured MAQ AI client.
    """
    session = get_session_for_user(db, user, session_id)
    text = (content or "").strip()
    if not text:
        raise HTTPException(422, "Message content is required")
    if len(text) > 4000:
        raise HTTPException(422, "Message too long (max 4000 chars)")

    user_msg = _add_message(db, session, "user", text)
    if session.title == "New conversation":
        session.title = _title_from_message(text)
    # Keep the user turn and assistant turn in one transaction. If the LLM or
    # a tool fails, a retry must not leave two stored user messages behind.
    db.flush()

    client = llm_client if llm_client is not None else get_llm_client()
    if not client:
        raise HTTPException(503, "LLM provider is not configured")

    assistant_text = ""
    tool_results: list[dict[str, Any]] = []
    pending_action: dict[str, Any] | None = None

    try:
        convo = [{"role": "system", "content": _system_prompt(user)}]
        convo += _history_for_llm(db, session)  # includes the just-saved user turn

        for _ in range(6):  # bounded loop; keep in sync with supervisor_max_iterations
            response = client.chat_with_tools(
                messages=convo,
                tools=chat_tools.tools_for_role(user.role),
            )
            message = response.choices[0].message

            if not message.tool_calls:
                assistant_text = message.content or ""
                break

            # Echo the assistant's tool-call request back for a valid transcript.
            convo.append({
                "role": "assistant",
                "content": message.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in message.tool_calls
                ],
            })

            awaiting = False
            for tc in message.tool_calls:
                name = tc.function.name
                try:
                    tool_args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    tool_args = {}

                if chat_tools.toolRequiresConfirmation(name):
                    pending_action = {
                        "name": name,
                        "arguments": tool_args,
                        "status": PENDING,
                        "expires_at": _pending_expires_at(),
                        "description": chat_tools.describe_action(db, user, name, tool_args),
                    }
                    awaiting = True
                    audit(
                        db, user=user, session=session, tool_name=name, event="proposed",
                        target_entity=name,
                        target_entity_id=tool_args.get("patient_id") or tool_args.get("journey_id"),
                        parameters=tool_args,
                    )
                    convo.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps({"status": "awaiting_confirmation"}),
                    })
                else:
                    try:
                        result = chat_tools.execute_tool(db, user, name, tool_args)
                        tool_results.append({"tool": name, "status": "ok", "result": result})
                        audit(
                            db, user=user, session=session, tool_name=name,
                            event="data_access", target_entity=name,
                            permission_result="allowed",
                        )
                        convo.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": json.dumps(result, default=str)[:4000],
                        })
                    except (chat_tools.ToolValidationError, HTTPException) as exc:
                        detail = getattr(exc, "detail", None) or str(exc)
                        tool_results.append({"tool": name, "status": "error", "error": detail})
                        audit(
                            db, user=user, session=session, tool_name=name,
                            event="denied", target_entity=name,
                            permission_result="denied", detail=detail,
                        )
                        convo.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": json.dumps({"status": "error", "error": detail}),
                        })

            if awaiting:
                break  # pause: the user must confirm before execution
        else:
            assistant_text = assistant_text or (
                "I could not complete that request — please rephrase or ask something else."
            )
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:  # noqa: BLE001 — surface LLM failures into the chat flow
        db.rollback()
        raise HTTPException(502, f"Assistant failed: {exc}")

    meta: dict[str, Any] = {}
    if tool_results:
        meta["tool_results"] = tool_results
    if pending_action:
        meta["pending_action"] = pending_action
        if not assistant_text:
            description = pending_action.get("description") or {}
            title = description.get("title", pending_action.get("name", "the action"))
            target = description.get("patient")
            assistant_text = (
                f"Please confirm: should I proceed with \"{title}\""
                + (f" for {target}" if target else "")
                + "?"
            )

    assistant_msg = _add_message(db, session, "assistant", assistant_text or "Done.", meta)
    db.commit()
    db.refresh(assistant_msg)
    db.refresh(session)
    return {"session": session, "user_message": user_msg, "assistant_message": assistant_msg}


def _set_pending_status(msg: ChatMessage, pending: dict[str, Any], status: str,
                        result: dict[str, Any] | None = None, error: str | None = None) -> None:
    pending["status"] = status
    if result is not None:
        pending["result"] = result
    if error is not None:
        pending["error"] = error
    meta = dict(msg.meta or {})
    meta["pending_action"] = pending
    msg.meta = meta
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(msg, "meta")


def confirm_action(db: Session, user: User, session_id: UUID, message_id: UUID) -> dict[str, Any]:
    """
    Execute the pending action attached to an assistant message. Re-validates
    ownership (session scoping), expiry, and authorization (execute_tool
    re-checks role + scope at execution time).
    """
    session = get_session_for_user(db, user, session_id)
    msg = db.query(ChatMessage).filter(
        ChatMessage.id == message_id, ChatMessage.session_id == session.id
    ).first()
    if not msg:
        raise HTTPException(404, "Message not found")
    meta = dict(msg.meta or {})
    pending = meta.get("pending_action")
    if not pending:
        raise HTTPException(422, "No pending action to confirm on this message")

    name = pending.get("name", "unknown")

    # Already resolved actions cannot be re-confirmed.
    if pending.get("status") not in (PENDING,):
        raise HTTPException(422, f"This action was already {pending.get('status', 'resolved')}")

    # Expired proposals never execute.
    if _pending_is_expired(pending):
        _set_pending_status(msg, pending, EXPIRED)
        audit(db, user=user, session=session, message=msg, tool_name=name,
              event="expired", target_entity=name,
              parameters=pending.get("arguments"))
        outcome_msg = _add_message(
            db, session, "assistant",
            "This action request has expired, so nothing was changed. Please ask me again if you still want to proceed.",
            {"action_result": {"message_id": str(msg.id), "tool": name, "status": EXPIRED}},
        )
        db.commit()
        db.refresh(outcome_msg)
        return {"session": session, "confirmed_message": msg, "result_message": outcome_msg}

    args = pending.get("arguments", {})
    audit(db, user=user, session=session, message=msg, tool_name=name,
          event="confirmed", target_entity=name, parameters=args)
    try:
        result = chat_tools.execute_tool(db, user, name, args)
        _set_pending_status(msg, pending, EXECUTED, result=result)
        audit(db, user=user, session=session, message=msg, tool_name=name,
              event="executed", target_entity=name,
              target_entity_id=(result.get("data", {}) or {}).get("journey", {}).get("id")
              if isinstance(result.get("data"), dict) else None,
              parameters=args, detail=result.get("summary"))
        outcome_text = result.get("summary", "Action completed.")
    except (chat_tools.ToolValidationError, HTTPException) as exc:
        detail = getattr(exc, "detail", None) or str(exc)
        _set_pending_status(msg, pending, FAILED, error=detail)
        audit(db, user=user, session=session, message=msg, tool_name=name,
              event="failed", target_entity=name, parameters=args,
              permission_result="denied" if "permission" in detail.lower() or "cannot" in detail.lower() else "allowed",
              detail=detail)
        outcome_text = f"The action could not be completed: {detail}"

    outcome_msg = _add_message(db, session, "assistant", outcome_text, {"action_result": {
        "message_id": str(msg.id),
        "tool": name,
        "status": pending["status"],
        "result": pending.get("result"),
        "error": pending.get("error"),
    }})
    db.commit()
    db.refresh(outcome_msg)
    db.refresh(session)
    return {"session": session, "confirmed_message": msg, "result_message": outcome_msg}


def reject_action(db: Session, user: User, session_id: UUID, message_id: UUID) -> dict[str, Any]:
    """Mark the pending action as rejected; nothing runs."""
    session = get_session_for_user(db, user, session_id)
    msg = db.query(ChatMessage).filter(
        ChatMessage.id == message_id, ChatMessage.session_id == session.id
    ).first()
    if not msg:
        raise HTTPException(404, "Message not found")
    meta = dict(msg.meta or {})
    pending = meta.get("pending_action")
    if not pending or pending.get("status") != PENDING:
        raise HTTPException(422, "No pending action on this message")

    name = pending.get("name", "unknown")
    _set_pending_status(msg, pending, REJECTED)
    audit(db, user=user, session=session, message=msg, tool_name=name,
          event="rejected", target_entity=name, parameters=pending.get("arguments"))
    db.commit()
    db.refresh(msg)
    return {"session": session, "message": msg}


def list_audit(db: Session, limit: int = 200) -> list[ChatAuditLog]:
    """Admin-facing audit trail (newest first)."""
    return (
        db.query(ChatAuditLog)
        .order_by(ChatAuditLog.created_at.desc())
        .limit(min(max(limit, 1), 500))
        .all()
    )
