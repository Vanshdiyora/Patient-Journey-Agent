from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy.orm import Session
from app.models import AgentRun

def record_agent_run(db: Session, journey_id, agent_name: str, run_type: str, input_context: dict, output: dict | None, tool_calls: list | None, status: str, error_message: str | None = None):
    now = datetime.now(timezone.utc)
    run = AgentRun(
        id=uuid4(), journey_id=journey_id, agent_name=agent_name, run_type=run_type,
        input_context=input_context, output=output, tool_calls=tool_calls or [], status=status,
        started_at=now, completed_at=None if status == "FAILED" else now, error_message=error_message,
    )
    db.add(run)
    db.flush()
    return run
