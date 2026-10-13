-- ============================================================
-- PATIENT JOURNEY ORCHESTRATOR
-- PostgreSQL Database Schema
-- ============================================================

-- ============================================================
-- 1. UUID EXTENSION
-- ============================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;


-- ============================================================
-- 2. ENUM TYPES
-- ============================================================

DO $$
BEGIN
    CREATE TYPE pathway_status AS ENUM (
    'DRAFT',
    'ACTIVE',
    'INACTIVE'
);
EXCEPTION WHEN duplicate_object THEN
    NULL;
END $$;

DO $$
BEGIN
    CREATE TYPE journey_status AS ENUM (
    'ACTIVE',
    'COMPLETED',
    'BLOCKED',
    'CANCELLED'
);
EXCEPTION WHEN duplicate_object THEN
    NULL;
END $$;

DO $$
BEGIN
    CREATE TYPE journey_priority AS ENUM (
    'LOW',
    'MEDIUM',
    'HIGH',
    'CRITICAL'
);
EXCEPTION WHEN duplicate_object THEN
    NULL;
END $$;

DO $$
BEGIN
    CREATE TYPE journey_step_status AS ENUM (
    'PENDING',
    'READY',
    'IN_PROGRESS',
    'BLOCKED',
    'OVERDUE',
    'COMPLETED',
    'CANCELLED'
);
EXCEPTION WHEN duplicate_object THEN
    NULL;
END $$;

DO $$
BEGIN
    CREATE TYPE dependency_condition AS ENUM (
    'COMPLETED',
    'RESULT_AVAILABLE',
    'APPROVED'
);
EXCEPTION WHEN duplicate_object THEN
    NULL;
END $$;

DO $$
BEGIN
    CREATE TYPE action_status AS ENUM (
    'REQUESTED',
    'EXECUTING',
    'SUCCESS',
    'FAILED',
    'CANCELLED'
);
EXCEPTION WHEN duplicate_object THEN
    NULL;
END $$;

DO $$
BEGIN
    CREATE TYPE action_requested_by AS ENUM (
    'SUPERVISOR',
    'COORDINATION',
    'HUMAN'
);
EXCEPTION WHEN duplicate_object THEN
    NULL;
END $$;

DO $$
BEGIN
    CREATE TYPE exception_severity AS ENUM (
    'LOW',
    'MEDIUM',
    'HIGH',
    'CRITICAL'
);
EXCEPTION WHEN duplicate_object THEN
    NULL;
END $$;

DO $$
BEGIN
    CREATE TYPE exception_status AS ENUM (
    'OPEN',
    'IN_PROGRESS',
    'RESOLVED',
    'DISMISSED'
);
EXCEPTION WHEN duplicate_object THEN
    NULL;
END $$;

DO $$
BEGIN
    CREATE TYPE agent_run_status AS ENUM (
    'SUCCESS',
    'FAILED'
);
EXCEPTION WHEN duplicate_object THEN
    NULL;
END $$;


-- ============================================================
-- 3. PATIENTS
-- ============================================================

CREATE TABLE patients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    patient_reference VARCHAR(50) NOT NULL UNIQUE,

    first_name VARCHAR(100) NOT NULL,

    last_name VARCHAR(100) NOT NULL,

    -- Optional for legacy imports; required for patient portal demo accounts.
    email VARCHAR(255) UNIQUE,

    date_of_birth DATE NOT NULL,

    gender VARCHAR(30),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- ============================================================
-- 4. PATHWAYS
-- ============================================================

CREATE TABLE pathways (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    code VARCHAR(100) NOT NULL,

    name VARCHAR(200) NOT NULL,

    description TEXT,

    version INTEGER NOT NULL DEFAULT 1,

    status pathway_status NOT NULL DEFAULT 'DRAFT',

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_pathway_code_version
        UNIQUE (code, version)
);


-- ============================================================
-- 5. PATHWAY STEPS
-- ============================================================

CREATE TABLE pathway_steps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    pathway_id UUID NOT NULL,

    code VARCHAR(100) NOT NULL,

    name VARCHAR(200) NOT NULL,

    description TEXT,

    step_type VARCHAR(50) NOT NULL,

    sequence_number INTEGER NOT NULL,

    required BOOLEAN NOT NULL DEFAULT TRUE,

    owner_role VARCHAR(30) NOT NULL DEFAULT 'CLINICIAN',

    due_after_days INTEGER,

    time_limit_hours INTEGER,

    completion_criteria JSONB,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_pathway_steps_pathway
        FOREIGN KEY (pathway_id)
        REFERENCES pathways(id)
        ON DELETE CASCADE,

    CONSTRAINT uq_pathway_step_code
        UNIQUE (pathway_id, code),

    CONSTRAINT uq_pathway_step_sequence
        UNIQUE (pathway_id, sequence_number),

    CONSTRAINT chk_due_after_days
        CHECK (
            due_after_days IS NULL
            OR due_after_days >= 0
        ),

    CONSTRAINT chk_pathway_step_owner_role
        CHECK (owner_role IN ('PATIENT', 'CLINICIAN', 'CARE_COORDINATOR', 'ADMIN', 'AGENT')),

    CONSTRAINT chk_pathway_step_time_limit_hours
        CHECK (time_limit_hours IS NULL OR time_limit_hours BETWEEN 1 AND 8760)
);


-- ============================================================
-- 6. DEPENDENCIES
-- ============================================================

CREATE TABLE dependencies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    pathway_id UUID NOT NULL,

    source_step_id UUID NOT NULL,

    target_step_id UUID NOT NULL,

    condition_type dependency_condition NOT NULL,

    condition_config JSONB,

    blocking BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_dependencies_pathway
        FOREIGN KEY (pathway_id)
        REFERENCES pathways(id)
        ON DELETE CASCADE,

    CONSTRAINT fk_dependencies_source_step
        FOREIGN KEY (source_step_id)
        REFERENCES pathway_steps(id)
        ON DELETE CASCADE,

    CONSTRAINT fk_dependencies_target_step
        FOREIGN KEY (target_step_id)
        REFERENCES pathway_steps(id)
        ON DELETE CASCADE,

    CONSTRAINT chk_dependency_different_steps
        CHECK (
            source_step_id <> target_step_id
        ),

    CONSTRAINT uq_dependency
        UNIQUE (
            source_step_id,
            target_step_id,
            condition_type
        )
);


-- ============================================================
-- 7. JOURNEYS
-- ============================================================

CREATE TABLE journeys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    patient_id UUID NOT NULL,

    pathway_id UUID NOT NULL,

    pathway_version INTEGER NOT NULL,

    status journey_status NOT NULL DEFAULT 'ACTIVE',

    priority journey_priority NOT NULL DEFAULT 'MEDIUM',

    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    target_completion_at TIMESTAMPTZ,

    completed_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_journeys_patient
        FOREIGN KEY (patient_id)
        REFERENCES patients(id)
        ON DELETE RESTRICT,

    CONSTRAINT fk_journeys_pathway
        FOREIGN KEY (pathway_id)
        REFERENCES pathways(id)
        ON DELETE RESTRICT
);


-- ============================================================
-- 8. JOURNEY STEPS
-- ============================================================

CREATE TABLE journey_steps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    journey_id UUID NOT NULL,

    pathway_step_id UUID NOT NULL,

    status journey_step_status NOT NULL DEFAULT 'PENDING',

    owner_role VARCHAR(30) NOT NULL DEFAULT 'CLINICIAN',

    time_limit_hours INTEGER,

    due_at TIMESTAMPTZ,

    started_at TIMESTAMPTZ,

    completed_at TIMESTAMPTZ,

    block_reason TEXT,

    last_evaluated_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_journey_steps_journey
        FOREIGN KEY (journey_id)
        REFERENCES journeys(id)
        ON DELETE CASCADE,

    CONSTRAINT fk_journey_steps_pathway_step
        FOREIGN KEY (pathway_step_id)
        REFERENCES pathway_steps(id)
        ON DELETE RESTRICT,

    CONSTRAINT uq_journey_pathway_step
        UNIQUE (
            journey_id,
            pathway_step_id
        ),

    CONSTRAINT chk_journey_step_owner_role
        CHECK (owner_role IN ('PATIENT', 'CLINICIAN', 'CARE_COORDINATOR', 'ADMIN', 'AGENT')),

    CONSTRAINT chk_journey_step_time_limit_hours
        CHECK (time_limit_hours IS NULL OR time_limit_hours BETWEEN 1 AND 8760)
);


-- ============================================================
-- 9. PATIENT EVENTS
-- ============================================================

CREATE TABLE patient_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    patient_id UUID NOT NULL,

    journey_id UUID NOT NULL,

    event_type VARCHAR(100) NOT NULL,

    source VARCHAR(100) NOT NULL,

    external_event_id VARCHAR(200),

    event_time TIMESTAMPTZ NOT NULL,

    payload JSONB,

    processed BOOLEAN NOT NULL DEFAULT FALSE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_patient_events_patient
        FOREIGN KEY (patient_id)
        REFERENCES patients(id)
        ON DELETE CASCADE,

    CONSTRAINT fk_patient_events_journey
        FOREIGN KEY (journey_id)
        REFERENCES journeys(id)
        ON DELETE CASCADE,

    CONSTRAINT uq_external_event
        UNIQUE (
            source,
            external_event_id
        )
);


-- ============================================================
-- 10. PATHWAY ACTION RULES
-- ============================================================

CREATE TABLE pathway_action_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    pathway_step_id UUID NOT NULL,

    action_type VARCHAR(100) NOT NULL,

    enabled BOOLEAN NOT NULL DEFAULT TRUE,

    requires_approval BOOLEAN NOT NULL DEFAULT FALSE,

    conditions JSONB,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_action_rules_pathway_step
        FOREIGN KEY (pathway_step_id)
        REFERENCES pathway_steps(id)
        ON DELETE CASCADE,

    CONSTRAINT uq_pathway_step_action
        UNIQUE (
            pathway_step_id,
            action_type
        )
);


-- ============================================================
-- 11. ACTION EXECUTIONS
-- ============================================================

CREATE TABLE action_executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    journey_id UUID NOT NULL,

    journey_step_id UUID,

    action_type VARCHAR(100) NOT NULL,

    requested_by action_requested_by NOT NULL,

    status action_status NOT NULL DEFAULT 'REQUESTED',

    idempotency_key VARCHAR(200) NOT NULL UNIQUE,

    request_payload JSONB,

    response_payload JSONB,

    requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    completed_at TIMESTAMPTZ,

    error_message TEXT,

    CONSTRAINT fk_action_executions_journey
        FOREIGN KEY (journey_id)
        REFERENCES journeys(id)
        ON DELETE CASCADE,

    CONSTRAINT fk_action_executions_journey_step
        FOREIGN KEY (journey_step_id)
        REFERENCES journey_steps(id)
        ON DELETE SET NULL
);


-- ============================================================
-- 12. EXCEPTIONS
-- ============================================================

CREATE TABLE exceptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    journey_id UUID NOT NULL,

    journey_step_id UUID,

    severity exception_severity NOT NULL,

    exception_type VARCHAR(100) NOT NULL,

    title VARCHAR(200) NOT NULL,

    description TEXT NOT NULL,

    status exception_status NOT NULL DEFAULT 'OPEN',

    recommended_action TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    resolved_at TIMESTAMPTZ,

    CONSTRAINT fk_exceptions_journey
        FOREIGN KEY (journey_id)
        REFERENCES journeys(id)
        ON DELETE CASCADE,

    CONSTRAINT fk_exceptions_journey_step
        FOREIGN KEY (journey_step_id)
        REFERENCES journey_steps(id)
        ON DELETE SET NULL
);


-- ============================================================
-- 13. AGENT RUNS
-- ============================================================

CREATE TABLE agent_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    journey_id UUID NOT NULL,

    agent_name VARCHAR(100) NOT NULL,

    run_type VARCHAR(50) NOT NULL,

    input_context JSONB,

    output JSONB,

    tool_calls JSONB,

    status agent_run_status NOT NULL,

    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    completed_at TIMESTAMPTZ,

    error_message TEXT,

    CONSTRAINT fk_agent_runs_journey
        FOREIGN KEY (journey_id)
        REFERENCES journeys(id)
        ON DELETE CASCADE
);


-- ============================================================
-- 14. INDEXES
-- ============================================================

-- Journeys

CREATE INDEX idx_journeys_patient_id
    ON journeys(patient_id);

CREATE INDEX idx_journeys_pathway_id
    ON journeys(pathway_id);

CREATE INDEX idx_journeys_status
    ON journeys(status);

CREATE INDEX idx_journeys_priority
    ON journeys(priority);


-- Pathway Steps

CREATE INDEX idx_pathway_steps_pathway_id
    ON pathway_steps(pathway_id);


-- Dependencies

CREATE INDEX idx_dependencies_source_step
    ON dependencies(source_step_id);

CREATE INDEX idx_dependencies_target_step
    ON dependencies(target_step_id);


-- Journey Steps

CREATE INDEX idx_journey_steps_journey_id
    ON journey_steps(journey_id);

CREATE INDEX idx_journey_steps_status
    ON journey_steps(status);

CREATE INDEX idx_journey_steps_due_at
    ON journey_steps(due_at);


-- Patient Events

CREATE INDEX idx_patient_events_patient_id
    ON patient_events(patient_id);

CREATE INDEX idx_patient_events_journey_id
    ON patient_events(journey_id);

CREATE INDEX idx_patient_events_event_type
    ON patient_events(event_type);

CREATE INDEX idx_patient_events_event_time
    ON patient_events(event_time);

CREATE INDEX idx_patient_events_processed
    ON patient_events(processed);


-- Action Rules

CREATE INDEX idx_action_rules_pathway_step
    ON pathway_action_rules(pathway_step_id);


-- Action Executions

CREATE INDEX idx_action_executions_journey_id
    ON action_executions(journey_id);

CREATE INDEX idx_action_executions_status
    ON action_executions(status);

CREATE INDEX idx_action_executions_action_type
    ON action_executions(action_type);


-- Exceptions

CREATE INDEX idx_exceptions_journey_id
    ON exceptions(journey_id);

CREATE INDEX idx_exceptions_status
    ON exceptions(status);

CREATE INDEX idx_exceptions_severity
    ON exceptions(severity);


-- Agent Runs

CREATE INDEX idx_agent_runs_journey_id
    ON agent_runs(journey_id);

CREATE INDEX idx_agent_runs_agent_name
    ON agent_runs(agent_name);

CREATE INDEX idx_agent_runs_started_at
    ON agent_runs(started_at);


-- ============================================================
-- 15. VERIFICATION
-- ============================================================

SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;


-- ============================================================
-- 14. USERS
-- ============================================================
-- Stores application users and bcrypt password hashes. Raw passwords are never stored.
-- ============================================================

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Login email
    email VARCHAR(255) NOT NULL UNIQUE,

    -- Display name shown in the application
    display_name VARCHAR(200) NOT NULL,

    -- Application role
    role VARCHAR(50) NOT NULL,

    -- Bcrypt hash used by email/password authentication.
    password_hash TEXT NOT NULL,

    -- Patient portal identities link to their one patient record; NULL for staff.
    patient_id UUID UNIQUE REFERENCES patients(id),

    -- Whether the user can access the application
    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_user_role
        CHECK (
            role IN (
                'ADMIN',
                'CARE_COORDINATOR',
                'CLINICIAN',
                'PATIENT'
            )
        )
);


-- ============================================================
-- USERS INDEXES
-- ============================================================

CREATE INDEX idx_users_email
    ON users(email);

CREATE INDEX idx_users_role
    ON users(role);

CREATE INDEX idx_users_active
    ON users(is_active);

-- One responsible clinician per patient; a clinician may have many patients.
ALTER TABLE patients ADD COLUMN assigned_clinician_id UUID REFERENCES users(id);
CREATE INDEX idx_patients_assigned_clinician_id ON patients(assigned_clinician_id);

-- Staff patient grants; no grant means no patient access for clinical staff.
CREATE TABLE staff_patient_assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    staff_user_id UUID NOT NULL REFERENCES users(id),
    patient_id UUID NOT NULL REFERENCES patients(id),
    assigned_by_user_id UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_staff_patient_assignment UNIQUE (staff_user_id, patient_id)
);
CREATE INDEX idx_staff_patient_assignments_staff_user_id ON staff_patient_assignments(staff_user_id);
CREATE INDEX idx_staff_patient_assignments_patient_id ON staff_patient_assignments(patient_id);
