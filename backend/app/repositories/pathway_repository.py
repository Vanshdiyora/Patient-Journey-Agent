from uuid import UUID
from sqlalchemy.orm import Session
from app.models import Pathway, PathwayStep, Dependency, PathwayActionRule

class PathwayRepository:
    def __init__(self, db: Session): self.db = db
    def get(self, pathway_id: UUID): return self.db.query(Pathway).filter(Pathway.id == pathway_id).first()
    def steps(self, pathway_id: UUID): return self.db.query(PathwayStep).filter(PathwayStep.pathway_id == pathway_id).order_by(PathwayStep.sequence_number).all()
    def dependencies(self, pathway_id: UUID): return self.db.query(Dependency).filter(Dependency.pathway_id == pathway_id).all()
    def action_rules_for_step(self, step_id: UUID): return self.db.query(PathwayActionRule).filter(PathwayActionRule.pathway_step_id == step_id, PathwayActionRule.enabled.is_(True)).all()
