import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class ChatAuditLog(Base):
    """
    Audit trail for chatbot activity, focused on state-changing actions.

    One row per recorded event: action proposed, confirmed, executed, failed,
    rejected or expired. Lets administrators answer who requested what, when,
    whether confirmation was obtained, and whether it succeeded.
    """
    __tablename__ = "chat_audit_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    role_at_time: Mapped[str | None] = mapped_column(String(30), nullable=True)
    correlation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True, nullable=True)
    patient_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True, nullable=True)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True, nullable=True)
    message_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    tool_name: Mapped[str] = mapped_column(String(100))
    event: Mapped[str] = mapped_column(String(30), index=True)
    # proposed | confirmed | executed | failed | rejected | expired
    target_entity: Mapped[str | None] = mapped_column(String(100), nullable=True)
    target_entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    parameters: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)
    permission_result: Mapped[str | None] = mapped_column(String(20), nullable=True)
    result_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, index=True)
