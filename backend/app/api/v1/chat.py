"""
Chat assistant REST API (any authenticated portal role).

Sessions and messages are always scoped to the authenticated user. The
confirm/reject endpoints complete the two-step action flow: the LLM proposes,
the user confirms in chat, only then does the tool execute.
"""
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.authorization import require_admin
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models import User
from app.services import chat_service

router = APIRouter(prefix="/chat", tags=["chat"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class SessionCreate(BaseModel):
    title: str | None = Field(default=None, max_length=200)


class SessionRename(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class MessageSend(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class SessionOut(BaseModel):
    id: UUID
    title: str
    is_archived: bool
    created_at: datetime
    updated_at: datetime


class MessageOut(BaseModel):
    id: UUID
    session_id: UUID
    role: str
    content: str
    meta: dict[str, Any] | None = None
    created_at: datetime


def _session_out(s) -> dict[str, Any]:
    return {
        "id": str(s.id),
        "title": s.title,
        "is_archived": bool(s.is_archived),
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }


def _message_out(m) -> dict[str, Any]:
    return {
        "id": str(m.id),
        "session_id": str(m.session_id),
        "role": m.role,
        "content": m.content,
        "meta": m.meta,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }


# ---------------------------------------------------------------------------
# Sessions (history)
# ---------------------------------------------------------------------------

@router.post("/sessions", status_code=201)
def create_session(
    body: SessionCreate | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    session = chat_service.create_session(db, user, body.title if body else None)
    return _session_out(session)


@router.get("/sessions")
def list_sessions(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return {"items": [_session_out(s) for s in chat_service.list_sessions(db, user)]}


@router.get("/sessions/{session_id}/messages")
def get_messages(
    session_id: UUID,
    limit: int = Query(200, ge=1, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = chat_service.get_messages(db, user, session_id, limit=limit)
    return {"items": [_message_out(m) for m in rows]}


@router.patch("/sessions/{session_id}")
def rename_session(
    session_id: UUID,
    body: SessionRename,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    session = chat_service.rename_session(db, user, session_id, body.title)
    return _session_out(session)


@router.delete("/sessions/{session_id}")
def archive_session(
    session_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    session = chat_service.archive_session(db, user, session_id)
    return _session_out(session)


# ---------------------------------------------------------------------------
# Messages (REST API for non-WebSocket clients)
# ---------------------------------------------------------------------------

@router.post("/sessions/{session_id}/messages", status_code=201)
def send_message(
    session_id: UUID,
    body: MessageSend,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = chat_service.process_user_message(db, user, session_id, body.content)
    return {
        "session": _session_out(result["session"]),
        "user_message": _message_out(result["user_message"]),
        "assistant_message": _message_out(result["assistant_message"]),
    }


# ---------------------------------------------------------------------------
# Two-step action confirmation
# ---------------------------------------------------------------------------

@router.post("/sessions/{session_id}/messages/{message_id}/confirm")
def confirm_action(
    session_id: UUID,
    message_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = chat_service.confirm_action(db, user, session_id, message_id)
    return {
        "session": _session_out(result["session"]),
        "confirmed_message": _message_out(result["confirmed_message"]),
        "result_message": _message_out(result["result_message"]),
    }


@router.post("/sessions/{session_id}/messages/{message_id}/reject")
def reject_action(
    session_id: UUID,
    message_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = chat_service.reject_action(db, user, session_id, message_id)
    return {
        "session": _session_out(result["session"]),
        "message": _message_out(result["message"]),
    }


# ---------------------------------------------------------------------------
# Audit trail (administrator only)
# ---------------------------------------------------------------------------

def _audit_out(row) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "user_id": str(row.user_id),
        "conversation_id": str(row.conversation_id) if row.conversation_id else None,
        "message_id": str(row.message_id) if row.message_id else None,
        "tool_name": row.tool_name,
        "event": row.event,
        "target_entity": row.target_entity,
        "target_entity_id": row.target_entity_id,
        "parameters": row.parameters,
        "permission_result": row.permission_result,
        "detail": row.detail,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


@router.get("/audit")
def chat_audit(
    limit: int = Query(200, ge=1, le=500),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Chatbot activity trail: who proposed/confirmed/executed what, and when."""
    rows = chat_service.list_audit(db, limit=limit)
    return {"items": [_audit_out(r) for r in rows]}
