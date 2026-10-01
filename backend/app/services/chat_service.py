"""
Chat assistant service layer.

Owns conversation persistence, the LLM tool-calling loop, and the two-step
"propose -> confirm -> execute" flow for mutating tools. All tool execution is
delegated to app.llm.tools which re-checks the user's authorization.
"""
import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.llm import tools as chat_tools
from app.llm.provider import get_llm_client
from app.models import ChatMessage, ChatSession, User

MAX_HISTORY_MESSAGES = 20

SYSTEM_PROMPT = (
    "You are CarePath Assistant, an in-app copilot for a patient-journey orchestrator. "
    "You help staff and patients inspect journeys and record updates.\n"
    "Rules:\n"
    "- Answer in the user's language, briefly and helpfully.\n"
    "- You may call tools to look up data or to record updates.\n"
    "- Mutating tools (submit_event, orchestrate_journey) REQUIRE explicit user confirmation. "
    "Propose the change in plain language with journey and event details; the app collects "
    "confirmation via the UI. Never claim a change is done unless a tool result says so.\n"
    "- If a journey id is missing, call list_journeys first or ask a short clarifying question.\n"
    "- Never invent journey ids, patient data, or medical advice."
)


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
    session.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(session)
    return session


def archive_session(db: Session, user: User, session_id: UUID) -> ChatSession:
    session = get_session_for_user(db, user, session_id)
    session.is_archived = True
    session.updated_at = datetime.now(timezone.utc)
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
    session.updated_at = datetime.now(timezone.utc)
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


def process_user_message(db: Session, user: User, session_id: UUID, content: str) -> dict[str, Any]:
    """
    Persist the user's message, run the LLM tool loop, persist the assistant
    turn. Mutating tool calls become a stored `pending_action` that the user
    must confirm in chat before anything executes.
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
    db.commit()

    client = get_llm_client()
    if not client:
        raise HTTPException(503, "LLM provider is not configured")

    assistant_text = ""
    tool_results: list[dict[str, Any]] = []
    pending_action: dict[str, Any] | None = None

    try:
        convo = [{"role": "system", "content": SYSTEM_PROMPT}]
        convo += _history_for_llm(db, session)  # includes the just-saved user turn

        for _ in range(settings.supervisor_max_iterations):
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
                    pending_action = {"name": name, "arguments": tool_args, "status": "pending"}
                    awaiting = True
                    convo.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps({"status": "awaiting_confirmation"}),
                    })
                else:
                    try:
                        result = chat_tools.execute_tool(db, user, name, tool_args)
                        tool_results.append({"tool": name, "status": "ok", "result": result})
                        convo.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": json.dumps(result, default=str)[:4000],
                        })
                    except (chat_tools.ToolValidationError, HTTPException) as exc:
                        detail = getattr(exc, "detail", None) or str(exc)
                        tool_results.append({"tool": name, "status": "error", "error": detail})
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
            proposed = json.dumps(pending_action.get("arguments", {}), default=str)
            assistant_text = (
                f"Please confirm: should I apply {pending_action.get('name')} with {proposed}?"
            )

    assistant_msg = _add_message(db, session, "assistant", assistant_text or "Done.", meta)
    db.commit()
    db.refresh(assistant_msg)
    db.refresh(session)
    return {"session": session, "user_message": user_msg, "assistant_message": assistant_msg}


def confirm_action(db: Session, user: User, session_id: UUID, message_id: UUID) -> dict[str, Any]:
    """Execute the pending action attached to an assistant message."""
    session = get_session_for_user(db, user, session_id)
    msg = db.query(ChatMessage).filter(
        ChatMessage.id == message_id, ChatMessage.session_id == session.id
    ).first()
    if not msg:
        raise HTTPException(404, "Message not found")
    meta = dict(msg.meta or {})
    pending = meta.get("pending_action")
    if not pending or pending.get("status") != "pending":
        raise HTTPException(422, "No pending action to confirm on this message")

    name = pending.get("name")
    args = pending.get("arguments", {})
    try:
        result = chat_tools.execute_tool(db, user, name, args)
        pending["status"] = "executed"
        pending["result"] = result
        outcome_text = result.get("summary", "Action completed.")
    except (chat_tools.ToolValidationError, HTTPException) as exc:
        detail = getattr(exc, "detail", None) or str(exc)
        pending["status"] = "failed"
        pending["error"] = detail
        outcome_text = f"The action could not be completed: {detail}"

    meta["pending_action"] = pending
    msg.meta = meta
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(msg, "meta")

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
    if not pending or pending.get("status") != "pending":
        raise HTTPException(422, "No pending action on this message")

    pending["status"] = "rejected"
    meta["pending_action"] = pending
    msg.meta = meta
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(msg, "meta")
    db.commit()
    db.refresh(msg)
    return {"session": session, "message": msg}
