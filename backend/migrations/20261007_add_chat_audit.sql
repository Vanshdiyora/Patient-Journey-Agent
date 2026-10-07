-- Chatbot audit trail: one row per recorded chatbot event (action proposed,
-- confirmed, executed, failed, rejected, expired). Admin-readable via
-- GET /api/v1/chat/audit.
CREATE TABLE IF NOT EXISTS chat_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    conversation_id UUID,
    message_id UUID,
    tool_name VARCHAR(100) NOT NULL,
    event VARCHAR(30) NOT NULL,
    target_entity VARCHAR(100),
    target_entity_id VARCHAR(64),
    parameters JSONB,
    permission_result VARCHAR(20),
    detail TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_chat_audit_log_user_id ON chat_audit_log (user_id);
CREATE INDEX IF NOT EXISTS ix_chat_audit_log_conversation_id ON chat_audit_log (conversation_id);
CREATE INDEX IF NOT EXISTS ix_chat_audit_log_event ON chat_audit_log (event);
CREATE INDEX IF NOT EXISTS ix_chat_audit_log_created_at ON chat_audit_log (created_at);
