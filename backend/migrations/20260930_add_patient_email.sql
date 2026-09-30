-- Patient contact email is optional for legacy/imported records. Portal-ready
-- patient records should have an email and a matching PATIENT users row.
CREATE EXTENSION IF NOT EXISTS pgcrypto;
ALTER TABLE patients ADD COLUMN IF NOT EXISTS email VARCHAR(255);

-- PostgreSQL permits multiple NULLs in a unique index, so legacy rows without
-- email remain valid while populated addresses stay unique.
CREATE UNIQUE INDEX IF NOT EXISTS ix_patients_email ON patients (email);

-- Replace external identity IDs with locally verified password hashes.
ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash TEXT;
UPDATE users
SET password_hash = crypt('Test@123', gen_salt('bf', 10))
WHERE users.password_hash IS NULL OR users.password_hash = '';
ALTER TABLE users ALTER COLUMN password_hash SET NOT NULL;
ALTER TABLE users DROP COLUMN IF EXISTS entra_object_id;

-- Link each portal patient identity to at most one patient record.
ALTER TABLE users ADD COLUMN IF NOT EXISTS patient_id UUID;
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'users_patient_id_fkey'
          AND conrelid = 'users'::regclass
    ) THEN
        ALTER TABLE users
            ADD CONSTRAINT users_patient_id_fkey
            FOREIGN KEY (patient_id) REFERENCES patients(id);
    END IF;
END $$;
-- Older versions may have created a non-unique ORM index with this name.
DROP INDEX IF EXISTS ix_users_patient_id;
CREATE UNIQUE INDEX ix_users_patient_id
    ON users (patient_id)
    WHERE patient_id IS NOT NULL;
