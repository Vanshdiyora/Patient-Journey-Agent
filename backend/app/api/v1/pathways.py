from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.authorization import require_admin
from app.core.database import get_db
from app.models import Pathway, PathwayStep
from app.schemas.pathway import PathwayCreate

router = APIRouter(prefix="/pathways", tags=["pathways"])


def _serialize_pathway(pathway: Pathway, steps: list[PathwayStep]) -> dict:
    return {
        "id": pathway.id,
        "code": pathway.code,
        "name": pathway.name,
        "description": pathway.description,
        "version": pathway.version,
        "status": pathway.status,
        "steps": [
            {
                "id": step.id,
                "code": step.code,
                "name": step.name,
                "description": step.description,
                "step_type": step.step_type,
                "sequence_number": step.sequence_number,
                "required": step.required,
                "time_limit_hours": step.time_limit_hours,
                "completion_criteria": step.completion_criteria,
            }
            for step in steps
        ],
    }


@router.get("")
def list_pathways(
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    pathways = db.query(Pathway).order_by(Pathway.name, Pathway.version.desc()).all()
    return [
        _serialize_pathway(
            pathway,
            db.query(PathwayStep)
            .filter(PathwayStep.pathway_id == pathway.id)
            .order_by(PathwayStep.sequence_number)
            .all(),
        )
        for pathway in pathways
    ]


@router.post("", status_code=201)
def create_pathway(
    data: PathwayCreate,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    if db.query(Pathway).filter(Pathway.code == data.code).first():
        raise HTTPException(409, "A pathway with this code already exists")

    now = datetime.now(timezone.utc)
    pathway = Pathway(
        id=uuid4(),
        code=data.code,
        name=data.name,
        description=data.description,
        version=1,
        status="ACTIVE",
        created_at=now,
        updated_at=now,
    )
    db.add(pathway)
    for sequence_number, template in enumerate(data.steps, start=1):
        db.add(
            PathwayStep(
                id=uuid4(),
                pathway_id=pathway.id,
                code=template.code,
                name=template.name,
                description=template.description,
                step_type=template.step_type,
                sequence_number=sequence_number,
                required=True,
                due_after_days=None,
                time_limit_hours=template.time_limit_hours,
                completion_criteria=template.completion_criteria,
                created_at=now,
                updated_at=now,
            )
        )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "A pathway with this code already exists") from exc
    db.refresh(pathway)
    steps = (
        db.query(PathwayStep)
        .filter(PathwayStep.pathway_id == pathway.id)
        .order_by(PathwayStep.sequence_number)
        .all()
    )
    return _serialize_pathway(pathway, steps)
