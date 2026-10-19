-- Bookings live on their journey activity; deadlines retain their clinical meaning.
ALTER TABLE journey_steps ADD COLUMN IF NOT EXISTS scheduled_start_at TIMESTAMPTZ;
ALTER TABLE journey_steps ADD COLUMN IF NOT EXISTS scheduled_end_at TIMESTAMPTZ;
ALTER TABLE journey_steps ADD COLUMN IF NOT EXISTS scheduled_staff_id UUID REFERENCES users(id);
ALTER TABLE journey_steps ADD COLUMN IF NOT EXISTS schedule_status VARCHAR(20);
ALTER TABLE journey_steps ADD COLUMN IF NOT EXISTS schedule_revision INTEGER NOT NULL DEFAULT 0;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_journey_step_booking') THEN
        ALTER TABLE journey_steps ADD CONSTRAINT chk_journey_step_booking CHECK (
            (scheduled_start_at IS NULL AND scheduled_end_at IS NULL AND schedule_status IS NULL AND scheduled_staff_id IS NULL)
            OR (scheduled_start_at IS NOT NULL AND scheduled_end_at IS NOT NULL AND scheduled_end_at > scheduled_start_at
                AND schedule_status IS NOT NULL AND schedule_status IN ('SCHEDULED', 'RESCHEDULED', 'CANCELLED'))
        );
    END IF;
END $$;
CREATE INDEX IF NOT EXISTS ix_journey_steps_scheduled_start_at ON journey_steps(scheduled_start_at);
CREATE INDEX IF NOT EXISTS ix_journey_steps_scheduled_staff_id ON journey_steps(scheduled_staff_id);
