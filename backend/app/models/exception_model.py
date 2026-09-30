import uuid
from datetime import datetime
from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID, ENUM
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base

exception_severity_enum = ENUM("CRITICAL","HIGH","MEDIUM","LOW", name="exception_severity", create_type=False)
exception_status_enum = ENUM("OPEN","IN_PROGRESS","RESOLVED","DISMISSED", name="exception_status", create_type=False)

class ExceptionRecord(Base):
    __tablename__ = "exceptions"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    journey_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    journey_step_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    severity: Mapped[str] = mapped_column(exception_severity_enum, index=True)
    exception_type: Mapped[str] = mapped_column(String)
    title: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(exception_status_enum, index=True)
    recommended_action: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
