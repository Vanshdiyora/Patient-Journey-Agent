from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.authorization import require_staff
from app.models import AgentRun, Journey
from app.schemas import AgentRunResponse

router = APIRouter()


@router.get("/agent-runs", response_model=list[AgentRunResponse])
def agent_runs(
    journey_id: UUID | None = None,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    user=Depends(require_staff),
):
    q = db.query(AgentRun)
    if journey_id:
        q = q.filter(AgentRun.journey_id == journey_id)
    else:
        # Restrict the global feed to journeys within the user's scope.
        from app.core.authorization import scope_patient_ids
        patient_ids = scope_patient_ids(db, user)
        if patient_ids is not None:
            q = q.join(Journey, Journey.id == AgentRun.journey_id).filter(
                Journey.patient_id.in_(patient_ids)
            )
    # The orchestration record spans its agent calls, so order by completion
    # to keep the final outcome ahead of the individual calls it summarizes.
    return q.order_by(AgentRun.completed_at.desc().nullslast(), AgentRun.started_at.desc()).limit(limit).all()
