-- Run only while initializing the synthetic demo database, after migrations.
-- The assignments below are demo fixtures; production patients are assigned by an admin.
WITH clinicians AS (
    SELECT id, row_number() OVER (ORDER BY id) AS ordinal,
           count(*) OVER () AS clinician_count
    FROM users WHERE role = 'CLINICIAN' AND is_active = true
)
UPDATE patients p
SET assigned_clinician_id = clinicians.id
FROM clinicians
WHERE p.patient_reference ~ '^PT-2026-[0-9]{6}$'
  AND clinicians.ordinal = (substring(p.patient_reference FROM '[0-9]+$')::integer % clinicians.clinician_count) + 1;

INSERT INTO staff_patient_assignments (staff_user_id, patient_id, assigned_by_user_id)
SELECT p.assigned_clinician_id, p.id, (SELECT id FROM users WHERE role = 'ADMIN' AND is_active = true ORDER BY id LIMIT 1)
FROM patients p
WHERE p.assigned_clinician_id IS NOT NULL
ON CONFLICT (staff_user_id, patient_id) DO NOTHING;

-- Give each step a specific responsible role based on the work it represents.
UPDATE pathway_steps
SET owner_role = CASE
    WHEN code = 'WEIGHT' THEN 'PATIENT'
    WHEN step_type = 'ADMIN' THEN 'ADMIN'
    WHEN step_type IN ('EDUCATION', 'FOLLOWUP', 'APPOINTMENT', 'REFERRAL', 'COUNSELLING') THEN 'CARE_COORDINATOR'
    ELSE 'CLINICIAN'
END
WHERE pathway_id IN (SELECT id FROM pathways WHERE code IN (
    'CARD-POST-PCI', 'ORTHO-TKA', 'ONCO-NEW', 'DIAB-ANNUAL', 'CHF-DISCHARGE', 'COPD-EXAC'
));
UPDATE journey_steps js SET owner_role = ps.owner_role
FROM pathway_steps ps WHERE js.pathway_step_id = ps.id
  AND ps.pathway_id IN (SELECT id FROM pathways WHERE code IN (
      'CARD-POST-PCI', 'ORTHO-TKA', 'ONCO-NEW', 'DIAB-ANNUAL', 'CHF-DISCHARGE', 'COPD-EXAC'
  ));

-- Anchor sample journeys near the day the database is seeded. Completed steps
-- precede the current step; upcoming steps have no misleading scheduled date.
UPDATE journeys j SET
    started_at = now() - ((10 + (substring(p.patient_reference FROM '[0-9]+$')::integer % 20)) * interval '1 day'),
    target_completion_at = now() + ((7 + (substring(p.patient_reference FROM '[0-9]+$')::integer % 20)) * interval '1 day'),
    completed_at = CASE WHEN j.status = 'COMPLETED' THEN now() - interval '1 day' ELSE NULL END,
    updated_at = now()
FROM patients p WHERE j.patient_id = p.id AND p.patient_reference ~ '^PT-2026-[0-9]{6}$';

UPDATE journey_steps js SET
    status = CASE WHEN j.status = 'COMPLETED' THEN 'COMPLETED' ELSE js.status END,
    started_at = CASE
        WHEN j.status = 'COMPLETED' OR js.status IN ('COMPLETED', 'READY', 'IN_PROGRESS', 'BLOCKED')
        THEN j.started_at + ((ps.sequence_number - 1) * interval '1 day') ELSE NULL END,
    completed_at = CASE
        WHEN j.status = 'COMPLETED' OR js.status = 'COMPLETED'
        THEN j.started_at + (ps.sequence_number * interval '1 day') ELSE NULL END,
    due_at = CASE
        WHEN j.status = 'COMPLETED' OR js.status = 'COMPLETED' THEN j.started_at + (ps.sequence_number * interval '2 days')
        WHEN js.status IN ('READY', 'IN_PROGRESS', 'BLOCKED') THEN now() + ((ps.sequence_number % 4 + 1) * interval '1 day')
        ELSE NULL END,
    block_reason = CASE WHEN j.status = 'COMPLETED' THEN NULL ELSE js.block_reason END,
    updated_at = now()
FROM journeys j, pathway_steps ps
WHERE js.journey_id = j.id AND js.pathway_step_id = ps.id
  AND EXISTS (SELECT 1 FROM patients p WHERE p.id = j.patient_id AND p.patient_reference ~ '^PT-2026-[0-9]{6}$');

-- Cancelled journeys keep their completed history and cancel unfinished work.
UPDATE journey_steps js SET status = 'CANCELLED', due_at = NULL,
    block_reason = NULL, updated_at = now()
FROM journeys j
WHERE js.journey_id = j.id AND j.status = 'CANCELLED' AND js.status <> 'COMPLETED'
  AND EXISTS (SELECT 1 FROM patients p WHERE p.id = j.patient_id AND p.patient_reference ~ '^PT-2026-[0-9]{6}$');

-- The original fixture marked the final step blocked as well as the actual
-- current step for some journeys. Keep only the first blocked step current.
UPDATE journey_steps js SET status = 'PENDING', block_reason = NULL,
    started_at = NULL, due_at = NULL, updated_at = now()
FROM pathway_steps ps
WHERE js.pathway_step_id = ps.id AND js.status = 'BLOCKED'
  AND ps.sequence_number = 8
  AND EXISTS (SELECT 1 FROM journeys j JOIN patients p ON p.id = j.patient_id
              WHERE j.id = js.journey_id AND p.patient_reference ~ '^PT-2026-[0-9]{6}$')
  AND EXISTS (
      SELECT 1 FROM journey_steps earlier
      JOIN pathway_steps earlier_template ON earlier_template.id = earlier.pathway_step_id
      WHERE earlier.journey_id = js.journey_id
        AND earlier.status = 'BLOCKED'
        AND earlier_template.sequence_number < ps.sequence_number
  );
