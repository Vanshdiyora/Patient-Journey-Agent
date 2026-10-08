from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.authorization import require_staff, scope_patient_ids
from app.models import AgentRun, Journey
from app.schemas import AgentRunResponse

router = APIRouter()


@router.get("/agent-runs")
def agent_runs(
    journey_id: UUID | None = None,
    run_id: UUID | None = None,
    limit: int = Query(10, ge=1, le=10),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user=Depends(require_staff),
):
    q = db.query(AgentRun).join(Journey, Journey.id == AgentRun.journey_id)
    if run_id:
        q = q.filter(AgentRun.id == run_id)
    if journey_id:
        q = q.filter(AgentRun.journey_id == journey_id)
    patient_ids = scope_patient_ids(db, user)
    if patient_ids is not None:
        q = q.filter(Journey.patient_id.in_(patient_ids))
    # The orchestration record spans its agent calls, so order by completion
    # to keep the final outcome ahead of the individual calls it summarizes.
    total = q.order_by(None).count()
    items = q.order_by(AgentRun.completed_at.desc().nullslast(), AgentRun.started_at.desc(), AgentRun.id.desc()).offset(offset).limit(limit).all()
    return {"items": [AgentRunResponse.model_validate(item).model_dump(mode="json") for item in items], "total": total, "limit": limit, "offset": offset}
