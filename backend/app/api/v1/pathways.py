from datetime import datetime, timezone
from math import ceil
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from app.core.authorization import require_admin
from app.core.database import get_db
from app.models import Dependency, Pathway, PathwayActionRule, PathwayStep
from app.schemas.pathway import PathwayCreate, PathwayUpdate

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
                "owner_role": step.owner_role,
                "time_limit_hours": step.time_limit_hours,
                "due_after_days": step.due_after_days,
                "completion_criteria": step.completion_criteria,
            }
            for step in steps
        ],
    }


@router.get("")
def list_pathways(
    limit: int = Query(10, ge=1, le=10),
    offset: int = Query(0, ge=0),
    latest_only: bool = False,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    q = db.query(Pathway)
    if latest_only:
        other = aliased(Pathway)
        latest = db.query(func.max(other.version)).filter(other.code == Pathway.code).correlate(Pathway).scalar_subquery()
        q = q.filter(Pathway.version == latest)
    total = q.count()
    pathways = q.order_by(Pathway.name, Pathway.version.desc(), Pathway.id.desc()).offset(offset).limit(limit).all()
    items = [
        _serialize_pathway(
            pathway,
            db.query(PathwayStep)
            .filter(PathwayStep.pathway_id == pathway.id)
            .order_by(PathwayStep.sequence_number)
            .all(),
        )
        for pathway in pathways
    ]
    return {"items": items, "total": total, "limit": limit, "offset": offset}


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
    previous_day = -1
    for sequence_number, template in enumerate(data.steps, start=1):
        target_day = template.due_after_days if template.due_after_days is not None else previous_day + max(1, ceil(template.time_limit_hours / 24))
        if target_day < previous_day:
            raise HTTPException(422, "Step target days must follow pathway order")
        previous_day = target_day
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
                owner_role=template.owner_role,
                due_after_days=target_day,
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


@router.put("/{pathway_id}")
def update_pathway(
    pathway_id: UUID,
    data: PathwayUpdate,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    # Updating the pathway creates a new version. Existing active journeys
    # sync lazily when their steps are next requested.
    previous = db.query(Pathway).filter(Pathway.id == pathway_id).with_for_update().first()
    if previous is None:
        raise HTTPException(404, "Pathway not found")
    if previous.status != "ACTIVE":
        raise HTTPException(409, "This pathway has changed. Reload and edit the active version")

    old_steps = (
        db.query(PathwayStep)
        .filter(PathwayStep.pathway_id == pathway_id)
        .order_by(PathwayStep.sequence_number)
        .all()
    )
    by_id = {step.id: step for step in old_steps}
    for step in data.steps:
        if step.id is not None and step.id not in by_id:
            raise HTTPException(422, "A step does not belong to this pathway")

    now = datetime.now(timezone.utc)
    updated = Pathway(
        id=uuid4(), code=previous.code, name=data.name,
        description=data.description, version=previous.version + 1,
        status="ACTIVE", created_at=now, updated_at=now,
    )
    db.add(updated)
    previous.status = "INACTIVE"
    previous.updated_at = now

    step_ids = {}
    previous_day = -1
    for sequence_number, template in enumerate(data.steps, start=1):
        source = by_id.get(template.id)
        target_day = template.due_after_days if template.due_after_days is not None else (source.due_after_days if source and source.due_after_days is not None else previous_day + max(1, ceil(template.time_limit_hours / 24)))
        if target_day < previous_day:
            raise HTTPException(422, "Step target days must follow pathway order")
        previous_day = target_day
        new_step = PathwayStep(
            id=uuid4(), pathway_id=updated.id, code=template.code,
            name=template.name, description=template.description,
            step_type=template.step_type, sequence_number=sequence_number,
            required=template.required, owner_role=template.owner_role,
            due_after_days=target_day,
            time_limit_hours=template.time_limit_hours,
            completion_criteria=template.completion_criteria if template.completion_criteria is not None else (source.completion_criteria if source else None),
            created_at=now, updated_at=now,
        )
        db.add(new_step)
        if source:
            step_ids[source.id] = new_step.id

    # These models use UUID columns without ORM relationships, so flush the
    # parent and steps before inserting rows with database foreign keys.
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Could not save this pathway version. Reload and try again") from exc

    # Keep workflow dependencies and action rules for steps retained in the edit.
    for dependency in db.query(Dependency).filter(Dependency.pathway_id == pathway_id).all():
        source_id = step_ids.get(dependency.source_step_id)
        target_id = step_ids.get(dependency.target_step_id)
        if source_id and target_id:
            db.add(Dependency(
                id=uuid4(), pathway_id=updated.id,
                source_step_id=source_id, target_step_id=target_id,
                condition_type=dependency.condition_type,
                condition_config=dependency.condition_config,
                blocking=dependency.blocking, created_at=now,
            ))
    if step_ids:
        for rule in db.query(PathwayActionRule).filter(PathwayActionRule.pathway_step_id.in_(step_ids)).all():
            db.add(PathwayActionRule(
                id=uuid4(), pathway_step_id=step_ids[rule.pathway_step_id],
                action_type=rule.action_type, enabled=rule.enabled,
                requires_approval=rule.requires_approval,
                conditions=rule.conditions, created_at=now,
            ))

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Could not save this pathway version. Reload and try again") from exc
    return _serialize_pathway(
        updated,
        db.query(PathwayStep)
        .filter(PathwayStep.pathway_id == updated.id)
        .order_by(PathwayStep.sequence_number)
        .all(),
    )
