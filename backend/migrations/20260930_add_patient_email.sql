-- Patient contact email is optional for legacy/imported records. Portal-ready
-- patient records should have an email and a matching PATIENT users row.
ALTER TABLE patients ADD COLUMN IF NOT EXISTS email VARCHAR;

-- PostgreSQL permits multiple NULL values in a unique index, so legacy rows
-- without email remain valid while populated email addresses stay unique.
CREATE UNIQUE INDEX IF NOT EXISTS ix_patients_email
    ON patients (email)
    WHERE email IS NOT NULL;
