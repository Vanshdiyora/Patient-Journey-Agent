ALTER TABLE pathway_steps
    ADD COLUMN IF NOT EXISTS time_limit_hours INTEGER;

ALTER TABLE journey_steps
    ADD COLUMN IF NOT EXISTS time_limit_hours INTEGER;

UPDATE pathway_steps
SET time_limit_hours = LEAST(GREATEST(COALESCE(due_after_days, 1), 1), 365) * 24
WHERE time_limit_hours IS NULL;

UPDATE journey_steps js
SET time_limit_hours = ps.time_limit_hours
FROM pathway_steps ps
WHERE js.pathway_step_id = ps.id
  AND js.time_limit_hours IS NULL;

UPDATE journey_steps
SET due_at = CASE
    WHEN status IN ('READY', 'IN_PROGRESS') AND time_limit_hours IS NOT NULL
        THEN COALESCE(started_at, updated_at, created_at, NOW())
             + (time_limit_hours * INTERVAL '1 hour')
    ELSE NULL
END
WHERE status NOT IN ('COMPLETED', 'CANCELLED');

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'ck_pathway_steps_time_limit_hours'
    ) THEN
        ALTER TABLE pathway_steps
            ADD CONSTRAINT ck_pathway_steps_time_limit_hours
            CHECK (time_limit_hours IS NULL OR time_limit_hours BETWEEN 1 AND 8760);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'ck_journey_steps_time_limit_hours'
    ) THEN
        ALTER TABLE journey_steps
            ADD CONSTRAINT ck_journey_steps_time_limit_hours
            CHECK (time_limit_hours IS NULL OR time_limit_hours BETWEEN 1 AND 8760);
    END IF;
END $$;
