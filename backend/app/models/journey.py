import uuid
from datetime import datetime
from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID, ENUM
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base

journey_status_enum = ENUM("ACTIVE","BLOCKED","COMPLETED","CANCELLED", name="journey_status", create_type=False)
journey_priority_enum = ENUM("CRITICAL","HIGH","MEDIUM","LOW", name="journey_priority", create_type=False)
journey_step_status_enum = ENUM("PENDING","READY","IN_PROGRESS","BLOCKED","COMPLETED","CANCELLED", name="journey_step_status", create_type=False)

class Journey(Base):
    __tablename__ = "journeys"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    pathway_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    pathway_version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(journey_status_enum, index=True)
    priority: Mapped[str] = mapped_column(journey_priority_enum, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    target_completion_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

class JourneyStep(Base):
    __tablename__ = "journey_steps"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    journey_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    pathway_step_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    status: Mapped[str] = mapped_column(journey_step_status_enum, index=True)
    owner_role: Mapped[str] = mapped_column(String, default="STAFF")
    time_limit_hours: Mapped[int | None] = mapped_column(Integer)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    block_reason: Mapped[str | None] = mapped_column(Text)
    last_evaluated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
