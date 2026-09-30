import uuid
from datetime import datetime
from typing import Any
from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base

class Dependency(Base):
    __tablename__ = "dependencies"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    pathway_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    source_step_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    target_step_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    condition_type: Mapped[str] = mapped_column(String)
    condition_config: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    blocking: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
