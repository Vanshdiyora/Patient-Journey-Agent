from datetime import datetime, timezone
from uuid import uuid4
import re
from sqlalchemy.orm import Session
from fastapi.encoders import jsonable_encoder
from app.models import AgentRun

# Each pattern keeps the label (group 1) and hides only the secret value.
_SECRET_PATTERNS = (
    re.compile(r"()(sk-[A-Za-z0-9._\-]+)"),
    re.compile(r"(Key Hash \(Token\)\s*=\s*)(\S+)", re.I),
    re.compile(r"(Received API Key\s*=\s*)(\S+)", re.I),
    re.compile(r"(Bearer\s+)([A-Za-z0-9._\-]+)", re.I),
    re.compile(r"((?:password|passwd|api[_-]?key|token|secret)\s*[=:]\s*)(\S+)", re.I),
)


def redact_secrets(text: str | None) -> str | None:
    """Stored error text must never carry API keys, key hashes or tokens."""
    if not text:
        return text
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub(lambda m: m.group(1) + "[redacted]", text)
    return text


def record_agent_run(db: Session, journey_id, agent_name: str, run_type: str, input_context: dict, output: dict | None, tool_calls: list | None, status: str, error_message: str | None = None, started_at: datetime | None = None):
    now = datetime.now(timezone.utc)
    run = AgentRun(
        id=uuid4(), journey_id=journey_id, agent_name=agent_name, run_type=run_type,
        input_context=jsonable_encoder(input_context), output=jsonable_encoder(output), tool_calls=jsonable_encoder(tool_calls or []), status=status,
        started_at=started_at or now, completed_at=now, error_message=redact_secrets(error_message),
    )
    db.add(run)
    db.flush()
    return run
