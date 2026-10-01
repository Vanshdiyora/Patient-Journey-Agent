"""
Chat WebSocket endpoint: /ws/chat?token=<JWT>

Protocol (JSON text frames):
- client -> server: {"type": "message", "content": "...", "session_id": "..."}
- client -> server: {"type": "ping"}
- server -> client: {"type": "typing", "session_id": "..."}
- server -> client: {"type": "message", "session_id": "...", "user_message": {...}, "assistant_message": {...}}
- server -> client: {"type": "error", "detail": "..."}
- server -> client: {"type": "pong"}

Authentication reuses the JWT from the REST API (passed as query param because
browsers cannot set headers on WebSocket). The DB session is opened per
message so the long-lived socket never holds a connection open.
"""
import json
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.auth import decode_token, load_authenticated_user
from app.core.database import SessionLocal
from app.services import chat_service

router = APIRouter()


def _message_out(m) -> dict:
    """Shape matching REST GET /chat/sessions/{id}/messages items."""
    return {
        "id": str(m.id),
        "session_id": str(m.session_id),
        "role": m.role,
        "content": m.content,
        "meta": m.meta,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }


@router.websocket("/ws/chat")
async def chat_socket(websocket: WebSocket):
    token = websocket.query_params.get("token", "")
    await websocket.accept()
    try:
        claims = decode_token(token)
    except Exception:
        await websocket.send_json({"type": "error", "detail": "Authentication failed"})
        await websocket.close(code=4401)
        return

    # Validate the user once up-front; each message re-loads the user in its
    # own DB session so the socket never pins a connection.
    try:
        db_probe = SessionLocal()
        user = load_authenticated_user(db_probe, claims)
        user_id = user.id
    except Exception:
        await websocket.send_json({"type": "error", "detail": "Authentication failed"})
        await websocket.close(code=4401)
        return
    finally:
        db_probe.close()

    while True:
        try:
            payload_raw = await websocket.receive_text()
        except WebSocketDisconnect:
            break

        try:
            payload = json.loads(payload_raw)
        except json.JSONDecodeError:
            await websocket.send_json({"type": "error", "detail": "Invalid JSON"})
            continue

        msg_type = payload.get("type")

        if msg_type == "ping":
            await websocket.send_json({"type": "pong"})
            continue

        if msg_type != "message":
            await websocket.send_json({"type": "error", "detail": f"Unknown type: {msg_type}"})
            continue

        content = str(payload.get("content") or "").strip()
        raw_session = payload.get("session_id")
        if not content:
            await websocket.send_json({"type": "error", "detail": "Message content is required"})
            continue
        if len(content) > 4000:
            await websocket.send_json({"type": "error", "detail": "Message too long (max 4000 chars)"})
            continue

        db = SessionLocal()
        try:
            user = load_authenticated_user(db, claims)
            if not raw_session:
                session = chat_service.create_session(db, user)
            else:
                try:
                    session_id = UUID(str(raw_session))
                except ValueError:
                    await websocket.send_json({"type": "error", "detail": "Invalid session id"})
                    continue
                session = chat_service.get_session_for_user(db, user, session_id)

            await websocket.send_json({
                "type": "typing",
                "session_id": str(session.id),
            })

            result = chat_service.process_user_message(db, user, session.id, content)
            await websocket.send_json({
                "type": "message",
                "session_id": str(session.id),
                "user_message": _message_out(result["user_message"]),
                "assistant_message": _message_out(result["assistant_message"]),
            })
        except Exception as exc:  # noqa: BLE001 — report failures to the client
            await websocket.send_json({"type": "error", "detail": str(exc)})
        finally:
            db.close()
