import uuid
from datetime import datetime
from typing import Any
from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB, ENUM
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base

action_requested_by_enum = ENUM("SUPERVISOR","COORDINATION","HUMAN", name="action_requested_by", create_type=False)
action_status_enum = ENUM("REQUESTED","EXECUTING","SUCCESS","FAILED","CANCELLED", name="action_status", create_type=False)

class ActionExecution(Base):
    __tablename__ = "action_executions"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    journey_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    journey_step_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    action_type: Mapped[str] = mapped_column(String, index=True)
    requested_by: Mapped[str] = mapped_column(action_requested_by_enum)
    status: Mapped[str] = mapped_column(action_status_enum, index=True)
    idempotency_key: Mapped[str] = mapped_column(String, unique=True, index=True)
    request_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    response_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)
