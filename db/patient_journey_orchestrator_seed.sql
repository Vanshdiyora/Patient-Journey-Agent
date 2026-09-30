-- ============================================================
-- Patient Journey Orchestrator - realistic production-style seed data
-- PostgreSQL / 12-table schema
--
-- Assumes the schema from the Patient Journey Orchestrator project
-- already exists, including the 10 enum types and the users table.
--
-- Volume:
--   1,200 staff users + 1,200 patient portal users
--   1,200 patients
--   6 pathways
--   48 pathway steps
--   42 dependencies
--   48 action rules
--   1,100 journeys
--   8,800 journey steps
--   6,600 patient events
--   ~2,200 action executions
--   ~1,100 exceptions
--   ~4,400 agent runs
--
-- IDs are deterministic so this script can be rerun safely after
-- clearing the seeded data. Names/emails and clinical-like data are
-- synthetic and do not represent real people. Every account starts with
-- Test@123; pgcrypto stores a separately salted bcrypt hash per user.
-- ============================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;

BEGIN;
-- Enum-backed columns use explicit casts below. This is required by PostgreSQL
-- when a CASE expression otherwise resolves to text.

-- Optional: only remove the deterministic seed dataset if it exists.
-- This makes rerunning the seed script predictable.
DELETE FROM agent_runs;
DELETE FROM exceptions;
DELETE FROM action_executions;
DELETE FROM patient_events;
DELETE FROM journey_steps;
DELETE FROM journeys;
DELETE FROM pathway_action_rules;
DELETE FROM dependencies;
DELETE FROM pathway_steps;
DELETE FROM pathways;
DELETE FROM users;
DELETE FROM patients;

-- ------------------------------------------------------------
-- 1. USERS / APPLICATION STAFF
-- ------------------------------------------------------------
INSERT INTO users (
    id, email, password_hash, display_name, role, patient_id, is_active,
    created_at, updated_at
)
SELECT
    (md5('user:' || gs::text))::uuid,
    lower(
        substr(first_names[((gs - 1) % 40) + 1], 1, 1)
        || '.'
        || regexp_replace(last_names[((gs - 1) % 50) + 1], '[^A-Za-z]', '', 'g')
        || lpad(gs::text, 4, '0')
        || '@carepath-health.example'
    ),
    crypt('Test@123', gen_salt('bf', 10)),
    first_names[((gs - 1) % 40) + 1] || ' ' || last_names[((gs - 1) % 50) + 1],
    CASE
        WHEN gs % 17 = 0 THEN 'ADMIN'
        WHEN gs % 3 = 0 THEN 'CLINICIAN'
        ELSE 'CARE_COORDINATOR'
    END,
    NULL,
    CASE WHEN gs % 31 = 0 THEN false ELSE true END,
    timestamptz '2025-01-06 09:00:00+05:30'
        + ((gs % 420) * interval '1 day')
        + ((gs % 8) * interval '1 hour'),
    timestamptz '2026-09-01 08:30:00+05:30'
        + ((gs % 28) * interval '1 day')
FROM generate_series(1,1200) gs
CROSS JOIN LATERAL (
    SELECT ARRAY[
        'Aarav','Aditi','Aditya','Akanksha','Ananya','Arjun','Bhavna','Dhruv',
        'Diya','Esha','Harsh','Ishaan','Jhanvi','Kabir','Karan','Kavya',
        'Meera','Mihir','Neha','Nikhil','Nisha','Parth','Pooja','Pranav',
        'Rahul','Rhea','Rohan','Riya','Sahil','Sakshi','Sameer','Shreya',
        'Tanvi','Varun','Vedant','Vikram','Yash','Zoya','Manav','Nandini'
    ]::text[] AS first_names
) fn
CROSS JOIN LATERAL (
    SELECT ARRAY[
        'Shah','Patel','Mehta','Desai','Joshi','Sharma','Verma','Kapoor',
        'Iyer','Nair','Menon','Reddy','Rao','Kulkarni','Pawar','Jadhav',
        'Chauhan','Solanki','Trivedi','Pandya','Dave','Bhat','Shetty','Gowda',
        'Malhotra','Bansal','Agarwal','Sinha','Mishra','Tiwari','Gupta','Singh',
        'Khan','Ansari','Thomas','Fernandes','D’Souza','Bose','Chatterjee','Das',
        'Banerjee','Mukherjee','Saxena','Kohli','Arora','Sethi','Chopra','Bedi',
        'Sodhi','Gill'
    ]::text[] AS last_names
) ln;

-- ------------------------------------------------------------
-- 2. PATIENTS
-- ------------------------------------------------------------
INSERT INTO patients (
    id, patient_reference, first_name, last_name, email, date_of_birth, gender,
    created_at, updated_at
)
SELECT
    (md5('patient:' || gs::text))::uuid,
    'PT-2026-' || lpad(gs::text, 6, '0'),
    first_names[((gs - 1) % 40) + 1],
    last_names[((gs * 7 - 1) % 50) + 1],
    'patient' || lpad(gs::text, 6, '0') || '@patient-demo.example.test',
    CASE
        WHEN gs % 29 = 0 THEN date '1942-03-17' + ((gs % 6000) * interval '1 day')
        WHEN gs % 7 = 0 THEN date '1980-01-01' + ((gs * 37) % 14000) * interval '1 day'
        ELSE date '1955-01-01' + ((gs * 53) % 22000) * interval '1 day'
    END::date,
    CASE gs % 4
        WHEN 0 THEN 'F'
        WHEN 1 THEN 'M'
        WHEN 2 THEN 'F'
        ELSE 'M'
    END,
    timestamptz '2024-10-01 09:00:00+05:30' + ((gs % 680) * interval '1 day'),
    timestamptz '2026-09-01 10:00:00+05:30' + ((gs % 28) * interval '1 day')
FROM generate_series(1,1200) gs
CROSS JOIN LATERAL (
    SELECT ARRAY[
        'Aarav','Aditi','Aditya','Akanksha','Ananya','Arjun','Bhavna','Dhruv',
        'Diya','Esha','Harsh','Ishaan','Jhanvi','Kabir','Karan','Kavya',
        'Meera','Mihir','Neha','Nikhil','Nisha','Parth','Pooja','Pranav',
        'Rahul','Rhea','Rohan','Riya','Sahil','Sakshi','Sameer','Shreya',
        'Tanvi','Varun','Vedant','Vikram','Yash','Zoya','Manav','Nandini'
    ]::text[] AS first_names
) fn
CROSS JOIN LATERAL (
    SELECT ARRAY[
        'Shah','Patel','Mehta','Desai','Joshi','Sharma','Verma','Kapoor',
        'Iyer','Nair','Menon','Reddy','Rao','Kulkarni','Pawar','Jadhav',
        'Chauhan','Solanki','Trivedi','Pandya','Dave','Bhat','Shetty','Gowda',
        'Malhotra','Bansal','Agarwal','Sinha','Mishra','Tiwari','Gupta','Singh',
        'Khan','Ansari','Thomas','Fernandes','D’Souza','Bose','Chatterjee','Das',
        'Banerjee','Mukherjee','Saxena','Kohli','Arora','Sethi','Chopra','Bedi',
        'Sodhi','Gill'
    ]::text[] AS last_names
) ln;

-- Every seeded patient receives a portal account linked to their patient row.
INSERT INTO users (
    id, email, password_hash, display_name, role, patient_id, is_active,
    created_at, updated_at
)
SELECT
    (md5('patient-user:' || p.patient_reference))::uuid,
    p.email,
    crypt('Test@123', gen_salt('bf', 10)),
    p.first_name || ' ' || p.last_name,
    'PATIENT',
    p.id,
    true,
    p.created_at,
    p.updated_at
FROM patients p;

-- ------------------------------------------------------------
-- 3. PATHWAYS
-- ------------------------------------------------------------
INSERT INTO pathways (
    id, code, name, description, version, status, created_at, updated_at
)
VALUES
((md5('pathway:1'))::uuid,'CARD-POST-PCI','Post-PCI Cardiac Recovery',
 'Structured recovery journey following coronary intervention, including medication reconciliation, wound review, cardiac rehabilitation and follow-up.',2,'ACTIVE',now()-interval '410 days',now()-interval '14 days'),
((md5('pathway:2'))::uuid,'ORTHO-TKA','Total Knee Replacement Recovery',
 'Perioperative and post-discharge pathway for total knee replacement with mobility, wound, pain and rehabilitation milestones.',3,'ACTIVE',now()-interval '390 days',now()-interval '9 days'),
((md5('pathway:3'))::uuid,'ONCO-NEW','New Oncology Treatment Start',
 'Coordinates baseline investigations, treatment readiness, education, authorization and early-cycle toxicity monitoring.',4,'ACTIVE',now()-interval '370 days',now()-interval '7 days'),
((md5('pathway:4'))::uuid,'DIAB-ANNUAL','Diabetes Annual Review',
 'Annual diabetes review covering laboratory monitoring, medication review, screening and care-plan follow-up.',2,'ACTIVE',now()-interval '350 days',now()-interval '12 days'),
((md5('pathway:5'))::uuid,'CHF-DISCHARGE','Heart Failure Discharge & 30-Day Support',
 'Discharge readiness and early post-discharge support for patients admitted with heart failure.',3,'ACTIVE',now()-interval '330 days',now()-interval '5 days'),
((md5('pathway:6'))::uuid,'COPD-EXAC','COPD Exacerbation Recovery',
 'Post-exacerbation pathway focused on medication reconciliation, symptom monitoring, pulmonary follow-up and prevention.',2,'ACTIVE',now()-interval '300 days',now()-interval '18 days');

-- ------------------------------------------------------------
-- 4. PATHWAY STEPS
-- ------------------------------------------------------------
WITH step_data(pathway_no, step_no, code, name, description, step_type, required, due_days, criteria) AS (
VALUES
(1,1,'MED-RECON','Medication reconciliation','Confirm discharge medicines, antiplatelet therapy and statin plan.','CLINICAL',true,1,'{"required":"medication_list_reviewed"}'),
(1,2,'WOUND-CHECK','Access-site / wound review','Review radial or femoral access site and post-procedure symptoms.','CLINICAL',true,3,'{"required":"wound_review_documented"}'),
(1,3,'CARD-FOLLOWUP','Cardiology follow-up','Confirm cardiology follow-up and review recovery progress.','APPOINTMENT',true,14,'{"required":"appointment_completed"}'),
(1,4,'CARDIAC-REHAB','Cardiac rehabilitation referral','Assess eligibility and send rehabilitation referral.','REFERRAL',true,14,'{"required":"referral_created"}'),
(1,5,'LIPID-LAB','Lipid monitoring','Obtain lipid profile where clinically due and review target.','LAB',false,30,'{"required":"lipid_result_available"}'),
(1,6,'RISK-REVIEW','Secondary prevention review','Review BP, smoking status, activity and cardiovascular risk factors.','CLINICAL',true,30,'{"required":"risk_review_completed"}'),
(1,7,'REHAB-START','Rehabilitation engagement','Confirm first rehabilitation session or documented alternative plan.','FOLLOWUP',false,45,'{"required":"rehab_engagement_recorded"}'),
(1,8,'POST-PCI-CLOSE','30-day pathway review','Close pathway after recovery and outstanding issue review.','CLOSURE',true,30,'{"required":"review_completed"}'),

(2,1,'PREOP-REVIEW','Pre-operative review','Confirm pre-operative assessment and surgical readiness.','CLINICAL',true,0,'{"required":"preop_clearance"}'),
(2,2,'SURGERY','Procedure completed','Confirm total knee replacement procedure and immediate recovery.','PROCEDURE',true,1,'{"required":"procedure_recorded"}'),
(2,3,'DISCHARGE','Discharge readiness','Validate pain control, mobility plan, wound instructions and home support.','DISCHARGE',true,3,'{"required":"discharge_checklist_complete"}'),
(2,4,'WOUND','Wound check','Review incision, swelling and infection warning signs.','CLINICAL',true,10,'{"required":"wound_review_documented"}'),
(2,5,'PHYSIO','Physiotherapy plan','Confirm home or outpatient physiotherapy schedule.','THERAPY',true,7,'{"required":"physio_plan_active"}'),
(2,6,'ORTHO-FOLLOWUP','Orthopedic follow-up','Review mobility, pain and recovery milestones.','APPOINTMENT',true,21,'{"required":"appointment_completed"}'),
(2,7,'ROM','Range-of-motion assessment','Record functional recovery and range of motion.','CLINICAL',false,45,'{"required":"rom_documented"}'),
(2,8,'TKA-CLOSE','Recovery review','Complete pathway review and identify persistent limitations.','CLOSURE',true,60,'{"required":"review_completed"}'),

(3,1,'BASELINE-LABS','Baseline investigations','Confirm CBC, chemistry and other treatment-specific baseline investigations.','LAB',true,0,'{"required":"baseline_results_available"}'),
(3,2,'AUTH','Treatment authorization','Confirm authorization or financial clearance for planned treatment.','ADMIN',true,3,'{"required":"authorization_confirmed"}'),
(3,3,'EDUCATION','Treatment education','Document treatment education, expected effects and escalation guidance.','EDUCATION',true,5,'{"required":"education_completed"}'),
(3,4,'TREATMENT','Treatment initiation','Confirm first treatment administration.','PROCEDURE',true,7,'{"required":"treatment_recorded"}'),
(3,5,'TOXICITY','Early toxicity check','Review symptoms and early adverse effects after treatment start.','CLINICAL',true,14,'{"required":"toxicity_review"}'),
(3,6,'LAB-MONITOR','Treatment monitoring labs','Review treatment-specific laboratory monitoring.','LAB',true,21,'{"required":"monitoring_results_available"}'),
(3,7,'ONCO-FOLLOWUP','Oncology follow-up','Review treatment response, tolerance and next cycle plan.','APPOINTMENT',true,28,'{"required":"appointment_completed"}'),
(3,8,'CYCLE-REVIEW','Cycle readiness review','Confirm readiness or documented change to treatment plan.','CLOSURE',true,35,'{"required":"cycle_plan_documented"}'),

(4,1,'A1C','HbA1c review','Review latest HbA1c and trend.','LAB',true,0,'{"required":"a1c_result_available"}'),
(4,2,'RENAL','Renal monitoring','Review kidney function and urine albumin screening where due.','LAB',true,7,'{"required":"renal_results_available"}'),
(4,3,'MED-REVIEW','Medication review','Review diabetes medicines, adherence and adverse effects.','CLINICAL',true,10,'{"required":"medication_review"}'),
(4,4,'BP','Blood pressure review','Record BP and assess control against care plan.','CLINICAL',true,10,'{"required":"bp_recorded"}'),
(4,5,'EYE','Retinal screening','Confirm retinal screening status or referral.','SCREENING',false,30,'{"required":"eye_screening_status"}'),
(4,6,'FOOT','Foot assessment','Complete foot-risk screening and education.','SCREENING',true,30,'{"required":"foot_assessment"}'),
(4,7,'LIFESTYLE','Lifestyle plan','Review nutrition, activity and self-management goals.','EDUCATION',true,30,'{"required":"lifestyle_plan"}'),
(4,8,'DIAB-CLOSE','Annual review close','Finalize annual care plan and next review date.','CLOSURE',true,45,'{"required":"care_plan_finalized"}'),

(5,1,'DISCHARGE-MEDS','Discharge medication reconciliation','Confirm diuretic, guideline-directed therapy and medication access.','DISCHARGE',true,1,'{"required":"medication_list_reviewed"}'),
(5,2,'WEIGHT','Weight monitoring plan','Confirm home weight monitoring and escalation threshold.','EDUCATION',true,2,'{"required":"weight_plan"}'),
(5,3,'PHONE-72H','72-hour check-in','Contact patient/caregiver and assess symptoms and access to medicines.','FOLLOWUP',true,3,'{"required":"contact_completed"}'),
(5,4,'LAB-7D','Early laboratory review','Review renal function/electrolytes when clinically due.','LAB',true,7,'{"required":"lab_review"}'),
(5,5,'HF-CLINIC','Heart failure follow-up','Complete early specialist or clinic review.','APPOINTMENT',true,14,'{"required":"appointment_completed"}'),
(5,6,'EDUCATION','Self-management reinforcement','Reinforce sodium/fluid plan, symptom recognition and escalation.','EDUCATION',true,14,'{"required":"education_completed"}'),
(5,7,'PHONE-30D','30-day check-in','Assess symptoms, adherence, readmissions and support needs.','FOLLOWUP',false,30,'{"required":"contact_completed"}'),
(5,8,'HF-CLOSE','30-day pathway close','Close journey or escalate unresolved clinical issues.','CLOSURE',true,35,'{"required":"review_completed"}'),

(6,1,'MED-RECON','Medication reconciliation','Confirm inhalers, steroids/antibiotics where applicable and home medicines.','CLINICAL',true,1,'{"required":"medication_list_reviewed"}'),
(6,2,'ACTION-PLAN','Exacerbation action plan','Confirm written action plan and warning signs.','EDUCATION',true,3,'{"required":"action_plan_documented"}'),
(6,3,'SMOKING','Smoking support review','Assess smoking status and offer cessation support when relevant.','COUNSELLING',false,7,'{"required":"smoking_support_status"}'),
(6,4,'PULM-FOLLOWUP','Pulmonary follow-up','Confirm follow-up after acute exacerbation.','APPOINTMENT',true,14,'{"required":"appointment_completed"}'),
(6,5,'INHALER','Inhaler technique review','Assess technique and adherence.','CLINICAL',true,21,'{"required":"technique_review"}'),
(6,6,'SPIROMETRY','Pulmonary function review','Review spirometry or latest available pulmonary function data.','LAB',false,30,'{"required":"pft_status"}'),
(6,7,'VACCINE','Prevention review','Review vaccination and prevention needs.','PREVENTION',false,30,'{"required":"prevention_review"}'),
(6,8,'COPD-CLOSE','Recovery close','Complete pathway review and prevention plan.','CLOSURE',true,35,'{"required":"review_completed"}')
)
INSERT INTO pathway_steps (
    id, pathway_id, code, name, description, step_type, sequence_number,
    required, due_after_days, completion_criteria, created_at, updated_at
)
SELECT
    (md5('pathway-step:' || pathway_no || ':' || step_no))::uuid,
    (md5('pathway:' || pathway_no))::uuid,
    code, name, description, step_type, step_no, required, due_days,
    criteria::jsonb,
    now()-interval '300 days',
    now()-interval '7 days'
FROM step_data;

-- ------------------------------------------------------------
-- 5. DEPENDENCIES
-- ------------------------------------------------------------
INSERT INTO dependencies (
    id, pathway_id, source_step_id, target_step_id, condition_type,
    condition_config, blocking, created_at
)
SELECT
    (md5('dependency:' || p || ':' || s))::uuid,
    (md5('pathway:' || p))::uuid,
    (md5('pathway-step:' || p || ':' || s))::uuid,
    (md5('pathway-step:' || p || ':' || (s+1)))::uuid,
    CASE
        WHEN s IN (2,4) THEN 'RESULT_AVAILABLE'
        WHEN s IN (3,5) THEN 'APPROVED'
        ELSE 'COMPLETED'
    END::dependency_condition,
    CASE
        WHEN s IN (2,4) THEN '{"required":true,"timeout_hours":72}'::jsonb
        WHEN s IN (3,5) THEN '{"required":true}'::jsonb
        ELSE '{"required":true}'::jsonb
    END,
    CASE WHEN s IN (1,2,3,5,6) THEN true ELSE false END,
    now()-interval '290 days'
FROM generate_series(1,6) p
CROSS JOIN generate_series(1,7) s;

-- ------------------------------------------------------------
-- 6. PATHWAY ACTION RULES
-- ------------------------------------------------------------
INSERT INTO pathway_action_rules (
    id, pathway_step_id, action_type, enabled, requires_approval,
    conditions, created_at
)
SELECT
    (md5('action-rule:' || p || ':' || s))::uuid,
    (md5('pathway-step:' || p || ':' || s))::uuid,
    CASE
        WHEN s IN (1,2) THEN 'CREATE_TASK'
        WHEN s IN (3,6) THEN 'SCHEDULE_APPOINTMENT'
        WHEN s = 4 THEN 'CREATE_REFERRAL'
        WHEN s = 5 THEN 'REQUEST_LAB'
        ELSE 'SEND_NOTIFICATION'
    END,
    true,
    CASE WHEN s IN (3,4) THEN true ELSE false END,
    CASE
        WHEN s = 1 THEN '{"when":"step_ready"}'
        WHEN s = 3 THEN '{"when":"appointment_missing","notify_hours":24}'
        WHEN s = 4 THEN '{"when":"referral_required"}'
        ELSE '{"when":"step_ready"}'
    END::jsonb,
    now()-interval '280 days'
FROM generate_series(1,6) p
CROSS JOIN generate_series(1,8) s;

-- ------------------------------------------------------------
-- 7. JOURNEYS
-- ------------------------------------------------------------
INSERT INTO journeys (
    id, patient_id, pathway_id, pathway_version, status, priority,
    started_at, target_completion_at, completed_at, created_at, updated_at
)
SELECT
    (md5('journey:' || gs::text))::uuid,
    (md5('patient:' || gs::text))::uuid,
    (md5('pathway:' || (((gs - 1) % 6) + 1)::text))::uuid,
    CASE ((gs - 1) % 6) + 1
        WHEN 1 THEN 2 WHEN 2 THEN 3 WHEN 3 THEN 4
        WHEN 4 THEN 2 WHEN 5 THEN 3 ELSE 2
    END,
    CASE
        WHEN gs % 23 = 0 THEN 'BLOCKED'
        WHEN gs % 19 = 0 THEN 'CANCELLED'
        WHEN gs % 7 = 0 THEN 'COMPLETED'
        ELSE 'ACTIVE'
    END::journey_status,
    CASE
        WHEN gs % 31 = 0 THEN 'CRITICAL'
        WHEN gs % 11 = 0 THEN 'HIGH'
        WHEN gs % 4 = 0 THEN 'MEDIUM'
        ELSE 'LOW'
    END::journey_priority,
    timestamptz '2026-06-01 08:00:00+05:30' - ((gs % 100) * interval '1 day'),
    timestamptz '2026-06-01 08:00:00+05:30' - ((gs % 100) * interval '1 day')
        + (((((gs - 1) % 6) + 1) * 7 + 20) * interval '1 day'),
    CASE WHEN gs % 7 = 0
        THEN timestamptz '2026-08-01 15:00:00+05:30' - ((gs % 60) * interval '1 day')
        ELSE NULL END,
    timestamptz '2026-05-20 09:00:00+05:30' - ((gs % 110) * interval '1 day'),
    timestamptz '2026-09-28 17:00:00+05:30' - ((gs % 12) * interval '1 day')
FROM generate_series(1,1100) gs;

-- ------------------------------------------------------------
-- 8. JOURNEY STEPS
-- ------------------------------------------------------------
INSERT INTO journey_steps (
    id, journey_id, pathway_step_id, status, due_at, started_at,
    completed_at, block_reason, last_evaluated_at, created_at, updated_at
)
SELECT
    (md5('journey-step:' || j || ':' || s))::uuid,
    (md5('journey:' || j))::uuid,
    (md5('pathway-step:' || (((j - 1) % 6) + 1) || ':' || s))::uuid,
    CASE
        WHEN s <= ((j - 1) % 8) THEN 'COMPLETED'
        WHEN s = (((j - 1) % 8) + 1) THEN
            CASE WHEN j % 23 = 0 THEN 'BLOCKED'
                 WHEN j % 5 = 0 THEN 'IN_PROGRESS'
                 ELSE 'READY' END
        WHEN j % 23 = 0 AND s = 8 THEN 'BLOCKED'
        ELSE 'PENDING'
    END::journey_step_status,
    (SELECT started_at FROM journeys WHERE id=(md5('journey:' || j))::uuid)
        + ((s * 4 + ((j - 1) % 6) * 3) * interval '1 day'),
    CASE WHEN s <= ((j - 1) % 8) + 1
        THEN (SELECT started_at FROM journeys WHERE id=(md5('journey:' || j))::uuid)
             + ((GREATEST(s-1,0) * 4) * interval '1 day')
        ELSE NULL END,
    CASE WHEN s <= ((j - 1) % 8)
        THEN (SELECT started_at FROM journeys WHERE id=(md5('journey:' || j))::uuid)
             + ((s * 4 - 1) * interval '1 day')
        ELSE NULL END,
    CASE WHEN j % 23 = 0 AND s = (((j - 1) % 8) + 1)
        THEN 'Pending clinical review or required result'
        ELSE NULL END,
    timestamptz '2026-09-29 08:00:00+05:30' - ((j % 5) * interval '1 day'),
    (SELECT created_at FROM journeys WHERE id=(md5('journey:' || j))::uuid),
    timestamptz '2026-09-29 18:00:00+05:30'
FROM generate_series(1,1100) j
CROSS JOIN generate_series(1,8) s;

-- ------------------------------------------------------------
-- 9. PATIENT EVENTS
-- ------------------------------------------------------------
INSERT INTO patient_events (
    id, patient_id, journey_id, event_type, source, external_event_id,
    event_time, payload, processed, created_at
)
SELECT
    (md5('event:' || j || ':' || e))::uuid,
    (md5('patient:' || j))::uuid,
    (md5('journey:' || j))::uuid,
    (ARRAY[
        'APPOINTMENT_BOOKED','LAB_RESULT_AVAILABLE','MEDICATION_UPDATED',
        'CLINICAL_NOTE_ADDED','PATIENT_CONTACTED','REFERRAL_CREATED',
        'DISCHARGE_COMPLETED','FOLLOWUP_COMPLETED'
    ])[((e-1)%8)+1],
    (ARRAY['EHR','LAB','PHARMACY','SCHEDULING','CARE_COORDINATION'])[((j+e-2)%5)+1],
    'EVT-' || to_char(2026,'FM0000') || '-' || lpad(j::text,5,'0') || '-' || lpad(e::text,2,'0'),
    (SELECT started_at FROM journeys WHERE id=(md5('journey:' || j))::uuid)
        + ((e * 3 + (j % 5)) * interval '1 day'),
    jsonb_build_object(
        'patient_reference','PT-2026-' || lpad(j::text,6,'0'),
        'event_sequence',e,
        'source_system',(ARRAY['EHR','LAB','PHARMACY','SCHEDULING','CARE_COORDINATION'])[((j+e-2)%5)+1],
        'summary',
        CASE ((e-1)%8)+1
            WHEN 1 THEN 'Follow-up appointment was scheduled.'
            WHEN 2 THEN 'Laboratory result became available for pathway review.'
            WHEN 3 THEN 'Medication list was reconciled with the latest encounter.'
            WHEN 4 THEN 'Clinical note was added by the care team.'
            WHEN 5 THEN 'Patient or caregiver contact was documented.'
            WHEN 6 THEN 'Referral was created and routed to the appropriate service.'
            WHEN 7 THEN 'Discharge milestone was documented.'
            ELSE 'Follow-up encounter was completed.'
        END
    ),
    CASE WHEN e < 6 OR j % 9 <> 0 THEN true ELSE false END,
    timestamptz '2026-06-01 10:00:00+05:30' + ((j % 90) * interval '1 day') + (e * interval '2 hours')
FROM generate_series(1,1100) j
CROSS JOIN generate_series(1,6) e;

-- ------------------------------------------------------------
-- 10. ACTION EXECUTIONS
-- ------------------------------------------------------------
INSERT INTO action_executions (
    id, journey_id, journey_step_id, action_type, requested_by, status,
    idempotency_key, request_payload, response_payload, requested_at,
    completed_at, error_message
)
SELECT
    (md5('execution:' || j || ':' || e))::uuid,
    (md5('journey:' || j))::uuid,
    (md5('journey-step:' || j || ':' || (((e-1)%8)+1)))::uuid,
    CASE ((e-1)%5)
        WHEN 0 THEN 'CREATE_TASK'
        WHEN 1 THEN 'SCHEDULE_APPOINTMENT'
        WHEN 2 THEN 'CREATE_REFERRAL'
        WHEN 3 THEN 'REQUEST_LAB'
        ELSE 'SEND_NOTIFICATION'
    END,
    CASE WHEN e % 3 = 0 THEN 'SUPERVISOR'
         WHEN e % 3 = 1 THEN 'COORDINATION'
         ELSE 'HUMAN' END::action_requested_by,
    CASE
        WHEN j % 29 = 0 AND e = 2 THEN 'FAILED'
        WHEN e = 3 THEN 'EXECUTING'
        ELSE 'SUCCESS'
    END::action_status,
    'PJX-' || j || '-' || e,
    jsonb_build_object(
        'patient_reference','PT-2026-' || lpad(j::text,6,'0'),
        'requested_action',CASE ((e-1)%5)
            WHEN 0 THEN 'CREATE_TASK'
            WHEN 1 THEN 'SCHEDULE_APPOINTMENT'
            WHEN 2 THEN 'CREATE_REFERRAL'
            WHEN 3 THEN 'REQUEST_LAB'
            ELSE 'SEND_NOTIFICATION' END
    ),
    CASE
        WHEN j % 29 = 0 AND e = 2
        THEN '{"accepted":false,"reason":"Downstream scheduling service timeout"}'::jsonb
        ELSE ('{"accepted":true,"external_reference":"EXT-' || j || '-' || e || '"}')::jsonb
    END,
    timestamptz '2026-07-01 09:00:00+05:30' + ((j % 75) * interval '1 day') + (e * interval '3 hours'),
    CASE
        WHEN j % 29 = 0 AND e = 2 THEN NULL
        WHEN e = 3 THEN NULL
        ELSE timestamptz '2026-07-01 12:00:00+05:30' + ((j % 75) * interval '1 day') + (e * interval '3 hours')
    END,
    CASE WHEN j % 29 = 0 AND e = 2 THEN 'Scheduling service timeout after retry policy exhausted.' ELSE NULL END
FROM generate_series(1,1100) j
CROSS JOIN generate_series(1,2) e;

-- ------------------------------------------------------------
-- 11. EXCEPTIONS
-- ------------------------------------------------------------
INSERT INTO exceptions (
    id, journey_id, journey_step_id, severity, exception_type, title,
    description, status, recommended_action, created_at, resolved_at
)
SELECT
    (md5('exception:' || j))::uuid,
    (md5('journey:' || j))::uuid,
    (md5('journey-step:' || j || ':' || (((j-1)%8)+1)))::uuid,
    CASE
        WHEN j % 37 = 0 THEN 'CRITICAL'
        WHEN j % 13 = 0 THEN 'HIGH'
        WHEN j % 5 = 0 THEN 'MEDIUM'
        ELSE 'LOW'
    END::exception_severity,
    CASE (j % 6)
        WHEN 0 THEN 'MISSING_RESULT'
        WHEN 1 THEN 'APPOINTMENT_DELAY'
        WHEN 2 THEN 'AUTHORIZATION_DELAY'
        WHEN 3 THEN 'PATIENT_UNREACHABLE'
        WHEN 4 THEN 'MEDICATION_ISSUE'
        ELSE 'DEPENDENCY_BLOCKED'
    END,
    CASE (j % 6)
        WHEN 0 THEN 'Required clinical result is not available'
        WHEN 1 THEN 'Follow-up appointment is delayed'
        WHEN 2 THEN 'Authorization is pending'
        WHEN 3 THEN 'Patient contact attempt was unsuccessful'
        WHEN 4 THEN 'Medication reconciliation requires review'
        ELSE 'Journey dependency is blocking progression'
    END,
    CASE (j % 6)
        WHEN 0 THEN 'The required result has not been received within the expected pathway window.'
        WHEN 1 THEN 'The scheduled follow-up is outside the target interval.'
        WHEN 2 THEN 'Treatment or service authorization remains unresolved.'
        WHEN 3 THEN 'Multiple contact attempts have not resulted in a completed interaction.'
        WHEN 4 THEN 'The medication list contains an unresolved discrepancy.'
        ELSE 'A prerequisite step has not reached the required completion state.'
    END,
    CASE
        WHEN j % 11 = 0 THEN 'RESOLVED'
        WHEN j % 17 = 0 THEN 'DISMISSED'
        WHEN j % 4 = 0 THEN 'IN_PROGRESS'
        ELSE 'OPEN'
    END::exception_status,
    CASE (j % 5)
        WHEN 0 THEN 'Route to care coordinator for same-day review.'
        WHEN 1 THEN 'Request missing result from source system.'
        WHEN 2 THEN 'Confirm next available appointment and update journey.'
        WHEN 3 THEN 'Escalate to clinical reviewer if unresolved.'
        ELSE 'Re-evaluate dependency after the next patient event.'
    END,
    timestamptz '2026-07-15 10:00:00+05:30' + ((j % 70) * interval '1 day'),
    CASE WHEN j % 11 = 0 OR j % 17 = 0
        THEN timestamptz '2026-08-15 16:00:00+05:30' + ((j % 25) * interval '1 day')
        ELSE NULL END
FROM generate_series(1,1100) j;

-- ------------------------------------------------------------
-- 12. AGENT RUNS
-- ------------------------------------------------------------
INSERT INTO agent_runs (
    id, journey_id, agent_name, run_type, input_context, output,
    tool_calls, status, started_at, completed_at, error_message
)
SELECT
    (md5('agent-run:' || j || ':' || r))::uuid,
    (md5('journey:' || j))::uuid,
    (ARRAY['ObservationAgent','InvestigationAgent','HypothesisAgent','ExperimentAgent'])[((r-1)%4)+1],
    CASE ((r-1)%4)
        WHEN 0 THEN 'OBSERVATION'
        WHEN 1 THEN 'INVESTIGATION'
        WHEN 2 THEN 'HYPOTHESIS'
        ELSE 'VALIDATION'
    END,
    jsonb_build_object(
        'patient_reference','PT-2026-' || lpad(j::text,6,'0'),
        'journey_id',md5('journey:' || j)::uuid,
        'trigger','scheduled_evaluation',
        'run_sequence',r
    ),
    CASE
        WHEN j % 41 = 0 AND r = 4
        THEN '{"finding":"Validation could not complete because an external dependency timed out.","confidence":0.42}'::jsonb
        ELSE jsonb_build_object(
            'finding',
            CASE ((r-1)%4)
                WHEN 0 THEN 'Recent pathway events were evaluated against the expected journey state.'
                WHEN 1 THEN 'Evidence was correlated across patient events and journey dependencies.'
                WHEN 2 THEN 'A likely blocking condition was identified for the next workflow step.'
                ELSE 'The proposed next action was validated against current journey state.'
            END,
            'confidence', round((0.78 + ((j % 20) / 100.0))::numeric,2),
            'recommended_next_step', 'Re-evaluate journey after the next qualifying event.'
        )
    END,
    jsonb_build_array(
        jsonb_build_object('tool','patient_event_store','operation','read_recent_events'),
        jsonb_build_object('tool','journey_state_store','operation','read_current_state')
    ),
    CASE WHEN j % 41 = 0 AND r = 4 THEN 'FAILED' ELSE 'SUCCESS' END::agent_run_status,
    timestamptz '2026-08-01 08:00:00+05:30'
        + ((j % 45) * interval '1 day') + ((r-1) * interval '2 hours'),
    CASE WHEN j % 41 = 0 AND r = 4 THEN NULL
         ELSE timestamptz '2026-08-01 08:07:00+05:30'
            + ((j % 45) * interval '1 day') + ((r-1) * interval '2 hours') END,
    CASE WHEN j % 41 = 0 AND r = 4
         THEN 'External scheduling dependency timed out during validation.'
         ELSE NULL END
FROM generate_series(1,1100) j
CROSS JOIN generate_series(1,4) r;

-- ------------------------------------------------------------
-- VALIDATION SUMMARY
-- ------------------------------------------------------------
SELECT 'users' AS table_name, count(*) AS row_count FROM users
UNION ALL SELECT 'patients', count(*) FROM patients
UNION ALL SELECT 'pathways', count(*) FROM pathways
UNION ALL SELECT 'pathway_steps', count(*) FROM pathway_steps
UNION ALL SELECT 'dependencies', count(*) FROM dependencies
UNION ALL SELECT 'pathway_action_rules', count(*) FROM pathway_action_rules
UNION ALL SELECT 'journeys', count(*) FROM journeys
UNION ALL SELECT 'journey_steps', count(*) FROM journey_steps
UNION ALL SELECT 'patient_events', count(*) FROM patient_events
UNION ALL SELECT 'action_executions', count(*) FROM action_executions
UNION ALL SELECT 'exceptions', count(*) FROM exceptions
UNION ALL SELECT 'agent_runs', count(*) FROM agent_runs
ORDER BY table_name;

COMMIT;
