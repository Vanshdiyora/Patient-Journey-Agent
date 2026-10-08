"""
Chat assistant service layer.

Owns conversation persistence, the LLM tool-calling loop, and the two-step
"propose -> confirm -> execute" flow for mutating tools. The LLM is never
trusted for permission decisions; for every tool call the server itself:

  1. denies tasks the user's role may not perform ("You are not permitted ..."),
  2. asks the user for any required information that is missing,
  3. validates arguments and scope without writing anything,
  4. asks the user to confirm every state-changing action before it runs,
  5. re-checks authorization when the confirmed action executes.

Every event (proposed / confirmed / executed / failed / rejected / expired /
denied / needs_info / data_access) is written to chat_audit_log.
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
    """Role-aware instructions. The role/scope are stated for grounding only —
    real authorization always happens server-side before any tool runs."""
    can, _cannot = chat_tools.role_capabilities(user.role)
    return (
        "You are CarePath Assistant, an in-app copilot for a patient-journey orchestrator. "
        "You look up data and carry out actions for the signed-in user by calling tools.\n"
        f"The signed-in user is {user.display_name}, role {user.role}; data scope: {scope_note(user)}.\n"
        f"Tasks this role can do: {', '.join(can)}.\n"
        "Rules:\n"
        "- Answer in the user's language, briefly and helpfully.\n"
        "- Get every fact by calling a tool; never answer from memory or invent ids, data or "
        "medical advice. Present tool results in plain language (names, not UUIDs).\n"
        "- If the user asks for ANY task, still call the matching tool even if you think their role "
        "may not allow it. The server decides permissions and replies with the standard "
        "'You are not permitted' message. Never refuse or explain permissions yourself.\n"
        "- If required information is missing or ambiguous, ask the user one short question "
        "instead of guessing. Resolve names yourself first: search_patients for patients, "
        "list_pathways for pathways, list_journeys / get_patient_summary / get_journey_steps for "
        "journeys and steps, list_users for users, list_exceptions for exceptions. If several "
        "match, list them and ask which one; if none match, say so.\n"
        "- Tools that change data (start_pathway, submit_event, complete_step, "
        "submit_step_update, update_step_time_limit, orchestrate_journey, update_exception, "
        "set_user_role, set_user_status, create_pathway) are never run directly: call the tool "
        "with complete arguments and the app shows the user a confirmation card. Do not ask for "
        "confirmation in text and never claim a change is done unless a tool result says so.\n"
        "- Propose one change at a time. If the user asks for something no tool supports, say you "
        "can't help with that."
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


def _error_text(exc: Exception) -> str:
    return str(getattr(exc, "detail", None) or exc)


def _handle_tool_call(
    db: Session, user: User, session: ChatSession, name: str, args: Any,
    pending_so_far: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    Gate one model-proposed tool call. Returns one of:
      final   - server-authored reply for the user (not permitted / info needed)
      pending - a mutating action stored for the user's confirmation
      result  - a read tool ran; its data goes back to the model
      error   - recoverable problem; the model gets the message and can retry/ask
    """
    args = args if isinstance(args, dict) else {}
    spec = chat_tools.get_spec(name)
    target_id = args.get("patient_id") or args.get("journey_id")

    def deny(reason: str | None = None) -> dict[str, Any]:
        text = chat_tools.denial_message(user, spec, reason)
        audit(db, user=user, session=session, tool_name=name, event="denied",
              target_entity=name, target_entity_id=target_id, parameters=args,
              permission_result="denied", detail=text)
        return {"kind": "final", "text": text,
                "notice": {"permission_denied": {"tool": name, "role": user.role}}}

    def error(text: str) -> dict[str, Any]:
        return {"kind": "error", "error": text,
                "tool_message": json.dumps({"status": "error", "error": text})}

    if spec is None:
        return error(f"Unknown tool: {name}")

    # 1. Role permission - decided by the server, never by the model.
    if not chat_tools.is_allowed(user, spec):
        return deny()

    # 2. Missing information - ask the user instead of guessing.
    args, missing = chat_tools.missing_arguments(db, user, spec, args)
    if missing:
        text = chat_tools.missing_message(db, spec, missing)
        audit(db, user=user, session=session, tool_name=name, event="needs_info",
              target_entity=name, parameters=args, detail="missing: " + ", ".join(missing))
        return {"kind": "final", "text": text, "notice": {"needs_info": {"tool": name, "missing": missing}}}

    # 3. Validation + scope checks (nothing is written).
    try:
        args = chat_tools.prepare_arguments(db, user, spec, args)
    except chat_tools.ToolPermissionError as exc:
        return deny(_error_text(exc))
    except HTTPException as exc:
        return deny(_error_text(exc)) if exc.status_code in (401, 403) else error(_error_text(exc))
    except chat_tools.ToolValidationError as exc:
        return error(_error_text(exc))

    # 4. Mutations are proposed, never run: the user confirms in the UI.
    if spec.confirm:
        if pending_so_far:
            return error("Only one change can be confirmed at a time; propose this one after the first is handled.")
        pending = {
            "name": name,
            "arguments": args,
            "status": PENDING,
            "expires_at": _pending_expires_at(),
            "description": chat_tools.describe_action(db, user, name, args),
        }
        audit(db, user=user, session=session, tool_name=name, event="proposed",
              target_entity=name, target_entity_id=target_id, parameters=args)
        return {"kind": "pending", "pending": pending,
                "tool_message": json.dumps({"status": "awaiting_confirmation"})}

    # 5. Reads run immediately, scoped to the user by the tool itself.
    try:
        result = chat_tools.execute_tool(db, user, name, args)
    except chat_tools.ToolPermissionError as exc:
        return deny(_error_text(exc))
    except HTTPException as exc:
        return deny(_error_text(exc)) if exc.status_code in (401, 403) else error(_error_text(exc))
    except chat_tools.ToolValidationError as exc:
        audit(db, user=user, session=session, tool_name=name, event="denied",
              target_entity=name, permission_result="denied", detail=_error_text(exc))
        return error(_error_text(exc))
    audit(db, user=user, session=session, tool_name=name, event="data_access",
          target_entity=name, permission_result="allowed")
    return {"kind": "result", "result": result,
            "tool_message": json.dumps(result, default=str)[:6000]}


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
    notice: dict[str, Any] = {}  # permission_denied / needs_info marker for the UI

    try:
        convo = [{"role": "system", "content": _system_prompt(user)}]
        convo += _history_for_llm(db, session)  # includes the just-saved user turn

        finished = False
        for _ in range(6):  # bounded loop; keep in sync with supervisor_max_iterations
            response = client.chat_with_tools(messages=convo, tools=chat_tools.tools_for_llm())
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

            for tc in message.tool_calls:
                try:
                    tool_args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    tool_args = {}
                outcome = _handle_tool_call(db, user, session, tc.function.name, tool_args, pending_action)

                if outcome["kind"] == "final":
                    # Server-authored reply (not permitted / need more info): stop here.
                    assistant_text = outcome["text"]
                    notice = outcome["notice"]
                    pending_action = None
                    finished = True
                    break
                if outcome["kind"] == "pending":
                    pending_action = outcome["pending"]
                elif outcome["kind"] == "result":
                    tool_results.append({"tool": tc.function.name, "status": "ok", "result": outcome["result"]})
                else:  # recoverable error: let the model fix its arguments or ask the user
                    tool_results.append({"tool": tc.function.name, "status": "error", "error": outcome["error"]})
                convo.append({"role": "tool", "tool_call_id": tc.id, "content": outcome["tool_message"]})

            if finished or pending_action:
                break  # a final reply, or the user must confirm before anything runs
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

    meta: dict[str, Any] = dict(notice)
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
    db.commit()  # keep the "confirmed" audit row even if execution fails and rolls back
    spec = chat_tools.get_spec(name)
    try:
        result = chat_tools.execute_tool(db, user, name, args)
        _set_pending_status(msg, pending, EXECUTED, result=result)
        audit(db, user=user, session=session, message=msg, tool_name=name,
              event="executed", target_entity=name,
              target_entity_id=(result.get("data") or {}).get("journey", {}).get("id")
              if isinstance(result.get("data"), dict) and isinstance(result["data"].get("journey"), dict) else None,
              parameters=args, detail=result.get("summary"))
        outcome_text = result.get("summary", "Action completed.")
    except (chat_tools.ToolValidationError, chat_tools.ToolPermissionError, HTTPException) as exc:
        db.rollback()  # discard anything the failed action half-wrote
        detail = _error_text(exc)
        denied = isinstance(exc, chat_tools.ToolPermissionError) or (
            isinstance(exc, HTTPException) and exc.status_code in (401, 403)
        )
        if denied:
            detail = chat_tools.denial_message(user, spec, detail)
        _set_pending_status(msg, pending, FAILED, error=detail)
        audit(db, user=user, session=session, message=msg, tool_name=name,
              event="failed", target_entity=name, parameters=args,
              permission_result="denied" if denied else "allowed", detail=detail)
        outcome_text = detail if denied else f"The action could not be completed: {detail}"

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
