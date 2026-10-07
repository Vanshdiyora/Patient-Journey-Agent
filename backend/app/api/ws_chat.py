"""Authenticated chat WebSocket at /ws/chat?token=<JWT>.

Each message has a client request_id. The typing, result, and error frames
echo that ID so the browser can match exactly one response to one send.
Database and LLM work runs in a worker thread with a session scoped to the
message; a long-lived socket does not hold a database connection.
"""
import json
from uuid import UUID

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from starlette.concurrency import run_in_threadpool

from app.auth import decode_token, load_authenticated_user
from app.core.database import SessionLocal
from app.services import chat_service

router = APIRouter()


def _message_out(message) -> dict:
    return {
        "id": str(message.id),
        "session_id": str(message.session_id),
        "role": message.role,
        "content": message.content,
        "meta": message.meta,
        "created_at": message.created_at.isoformat() if message.created_at else None,
    }


def _authenticate(claims) -> None:
    with SessionLocal() as db:
        load_authenticated_user(db, claims)


def _process_message(claims, raw_session, content) -> dict:
    with SessionLocal() as db:
        user = load_authenticated_user(db, claims)
        if raw_session:
            try:
                session_id = UUID(str(raw_session))
            except ValueError:
                raise HTTPException(422, "Invalid session id")
            session = chat_service.get_session_for_user(db, user, session_id)
        else:
            session = chat_service.create_session(db, user)
        result = chat_service.process_user_message(db, user, session.id, content)
        return {
            "session_id": str(session.id),
            "user_message": _message_out(result["user_message"]),
            "assistant_message": _message_out(result["assistant_message"]),
        }


def _resolve_action(claims, raw_session, raw_message, confirm: bool) -> dict:
    try:
        session_id = UUID(str(raw_session))
        message_id = UUID(str(raw_message))
    except (ValueError, TypeError):
        raise HTTPException(422, "Invalid session or message id")
    with SessionLocal() as db:
        user = load_authenticated_user(db, claims)
        result = (
            chat_service.confirm_action(db, user, session_id, message_id)
            if confirm else chat_service.reject_action(db, user, session_id, message_id)
        )
        return {
            "session_id": str(session_id),
            "message": _message_out(result.get("confirmed_message") or result["message"]),
            "result_message": _message_out(result["result_message"]) if result.get("result_message") else None,
        }


@router.websocket("/ws/chat")
async def chat_socket(websocket: WebSocket):
    await websocket.accept()
    try:
        claims = decode_token(websocket.query_params.get("token", ""))
        await run_in_threadpool(_authenticate, claims)
    except Exception:
        await websocket.send_json({"type": "error", "detail": "Authentication failed"})
        await websocket.close(code=4401)
        return

    while True:
        try:
            raw = await websocket.receive_text()
        except WebSocketDisconnect:
            break

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            await websocket.send_json({"type": "error", "detail": "Invalid JSON"})
            continue
        if not isinstance(payload, dict):
            await websocket.send_json({"type": "error", "detail": "Expected a JSON object"})
            continue

        request_id = payload.get("request_id")
        kind = payload.get("type")
        if kind == "ping":
            await websocket.send_json({"type": "pong", "request_id": request_id})
            continue
        if kind in ("confirm", "reject"):
            try:
                result = await run_in_threadpool(
                    _resolve_action, claims, payload.get("session_id"),
                    payload.get("message_id"), kind == "confirm",
                )
                await websocket.send_json({"type": "action", "request_id": request_id, **result})
            except Exception as exc:
                detail = exc.detail if isinstance(exc, HTTPException) else str(exc)
                await websocket.send_json({"type": "error", "request_id": request_id, "detail": detail})
            continue
        if kind != "message":
            await websocket.send_json({"type": "error", "request_id": request_id, "detail": f"Unknown type: {kind}"})
            continue

        content = str(payload.get("content") or "").strip()
        raw_session = payload.get("session_id")
        if not content or len(content) > 4000:
            detail = "Message content is required" if not content else "Message too long (max 4000 chars)"
            await websocket.send_json({"type": "error", "request_id": request_id, "detail": detail})
            continue

        try:
            await websocket.send_json({
                "type": "typing", "request_id": request_id,
                "session_id": str(raw_session) if raw_session else None,
            })
            result = await run_in_threadpool(_process_message, claims, raw_session, content)
            await websocket.send_json({"type": "message", "request_id": request_id, **result})
        except Exception as exc:
            detail = exc.detail if isinstance(exc, HTTPException) else str(exc)
            await websocket.send_json({"type": "error", "request_id": request_id, "detail": detail})
