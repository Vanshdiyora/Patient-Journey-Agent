ALTER TABLE pathway_steps
    ADD COLUMN IF NOT EXISTS owner_role VARCHAR(30) NOT NULL DEFAULT 'STAFF';

ALTER TABLE journey_steps
    ADD COLUMN IF NOT EXISTS owner_role VARCHAR(30) NOT NULL DEFAULT 'STAFF';

UPDATE pathway_steps SET owner_role = 'STAFF' WHERE owner_role IS NULL;
UPDATE journey_steps SET owner_role = 'STAFF' WHERE owner_role IS NULL;

ALTER TABLE pathway_steps ALTER COLUMN owner_role SET DEFAULT 'STAFF';
ALTER TABLE pathway_steps ALTER COLUMN owner_role SET NOT NULL;
ALTER TABLE journey_steps ALTER COLUMN owner_role SET DEFAULT 'STAFF';
ALTER TABLE journey_steps ALTER COLUMN owner_role SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'chk_pathway_step_owner_role'
    ) THEN
        ALTER TABLE pathway_steps
            ADD CONSTRAINT chk_pathway_step_owner_role
            CHECK (owner_role IN ('PATIENT', 'CLINICIAN', 'CARE_COORDINATOR', 'ADMIN', 'STAFF', 'AGENT'));
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'chk_journey_step_owner_role'
    ) THEN
        ALTER TABLE journey_steps
            ADD CONSTRAINT chk_journey_step_owner_role
            CHECK (owner_role IN ('PATIENT', 'CLINICIAN', 'CARE_COORDINATOR', 'ADMIN', 'STAFF', 'AGENT'));
    END IF;
END $$;
