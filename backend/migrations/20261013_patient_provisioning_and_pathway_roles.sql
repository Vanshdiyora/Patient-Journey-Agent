-- Existing patients remain unassigned until an administrator chooses a clinician.
ALTER TABLE patients ADD COLUMN IF NOT EXISTS assigned_clinician_id UUID REFERENCES users(id);
CREATE INDEX IF NOT EXISTS ix_patients_assigned_clinician_id ON patients(assigned_clinician_id);

-- Give legacy generic staff steps a named clinical owner. Preserve roles already set.
UPDATE pathway_steps SET owner_role = 'CLINICIAN' WHERE owner_role = 'STAFF';
UPDATE journey_steps SET owner_role = 'CLINICIAN' WHERE owner_role = 'STAFF';
ALTER TABLE pathway_steps ALTER COLUMN owner_role SET DEFAULT 'CLINICIAN';
ALTER TABLE journey_steps ALTER COLUMN owner_role SET DEFAULT 'CLINICIAN';
ALTER TABLE pathway_steps DROP CONSTRAINT IF EXISTS chk_pathway_step_owner_role;
ALTER TABLE journey_steps DROP CONSTRAINT IF EXISTS chk_journey_step_owner_role;
ALTER TABLE pathway_steps ADD CONSTRAINT chk_pathway_step_owner_role
    CHECK (owner_role IN ('PATIENT', 'CLINICIAN', 'CARE_COORDINATOR', 'ADMIN', 'AGENT'));
ALTER TABLE journey_steps ADD CONSTRAINT chk_journey_step_owner_role
    CHECK (owner_role IN ('PATIENT', 'CLINICIAN', 'CARE_COORDINATOR', 'ADMIN', 'AGENT'));
