-- Staff start with no patient access until an administrator grants it.
CREATE TABLE IF NOT EXISTS staff_patient_assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    staff_user_id UUID NOT NULL REFERENCES users(id),
    patient_id UUID NOT NULL REFERENCES patients(id),
    assigned_by_user_id UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_staff_patient_assignment UNIQUE (staff_user_id, patient_id)
);
CREATE INDEX IF NOT EXISTS ix_staff_patient_assignments_staff_user_id
    ON staff_patient_assignments(staff_user_id);
CREATE INDEX IF NOT EXISTS ix_staff_patient_assignments_patient_id
    ON staff_patient_assignments(patient_id);

ALTER TABLE chat_audit_log ADD COLUMN IF NOT EXISTS role_at_time VARCHAR(30);
ALTER TABLE chat_audit_log ADD COLUMN IF NOT EXISTS correlation_id UUID;
ALTER TABLE chat_audit_log ADD COLUMN IF NOT EXISTS patient_id UUID;
ALTER TABLE chat_audit_log ADD COLUMN IF NOT EXISTS result_status VARCHAR(30);
CREATE INDEX IF NOT EXISTS ix_chat_audit_log_correlation_id
    ON chat_audit_log(correlation_id);
CREATE INDEX IF NOT EXISTS ix_chat_audit_log_patient_id
    ON chat_audit_log(patient_id);

-- Previous versions copied full chat tool arguments (including free text) into
-- the audit table. Remove those payloads before making the table append-only.
DROP TRIGGER IF EXISTS chat_audit_append_only ON chat_audit_log;
UPDATE chat_audit_log
SET parameters = '{"legacy_redacted":true}'::jsonb,
    detail = NULL
WHERE parameters IS NOT NULL OR detail IS NOT NULL;

-- The application can append audit entries but must not rewrite their history.
CREATE OR REPLACE FUNCTION reject_chat_audit_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'chat audit entries are append-only';
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER chat_audit_append_only
BEFORE UPDATE OR DELETE ON chat_audit_log
FOR EACH ROW EXECUTE FUNCTION reject_chat_audit_mutation();
