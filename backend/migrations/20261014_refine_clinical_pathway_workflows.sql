-- Publish refined versions of the six seeded clinical pathways. Existing
-- completed journeys keep their historical versions; active journeys sync
-- lazily to the new versions through the regular journey service.
BEGIN;

CREATE TEMP TABLE pathway_refinement_map ON COMMIT DROP AS
SELECT
    pathway.id AS old_pathway_id,
    (md5('pathway:workflow-refinement:' || pathway.code))::uuid AS new_pathway_id,
    pathway.code,
    pathway.name,
    pathway.description,
    pathway.version AS old_version
FROM pathways pathway
JOIN (VALUES
    ('CARD-POST-PCI', 2),
    ('ORTHO-TKA', 3),
    ('ONCO-NEW', 4),
    ('DIAB-ANNUAL', 2),
    ('CHF-DISCHARGE', 3),
    ('COPD-EXAC', 2)
) AS seeded(code, version) ON seeded.code = pathway.code AND seeded.version = pathway.version
WHERE pathway.status = 'ACTIVE';

DO $$
BEGIN
    IF (SELECT count(*) FROM pathway_refinement_map) <> 6 THEN
        RAISE EXCEPTION 'Expected all six active seeded pathways at their source versions before refinement';
    END IF;
END $$;

INSERT INTO pathways (id, code, name, description, version, status, created_at, updated_at)
SELECT new_pathway_id, code, name, description, old_version + 1, 'ACTIVE', now(), now()
FROM pathway_refinement_map;

UPDATE pathways pathway
SET status = 'INACTIVE', updated_at = now()
FROM pathway_refinement_map refinement
WHERE pathway.id = refinement.old_pathway_id;

CREATE TEMP TABLE pathway_step_refinement_map ON COMMIT DROP AS
SELECT
    old_step.id AS old_step_id,
    refinement.old_pathway_id,
    refinement.new_pathway_id,
    old_step.code,
    (md5('pathway-step:workflow-refinement:' || refinement.code || ':' || old_step.code))::uuid AS new_step_id
FROM pathway_steps old_step
JOIN pathway_refinement_map refinement ON refinement.old_pathway_id = old_step.pathway_id;

INSERT INTO pathway_steps (
    id, pathway_id, code, name, description, step_type, sequence_number,
    required, owner_role, due_after_days, time_limit_hours,
    completion_criteria, created_at, updated_at
)
SELECT
    step_map.new_step_id,
    step_map.new_pathway_id,
    old_step.code,
    old_step.name,
    old_step.description,
    old_step.step_type,
    old_step.sequence_number,
    old_step.required,
    CASE
        WHEN old_step.code = 'WEIGHT' THEN 'PATIENT'
        WHEN old_step.code = 'AUTH' OR old_step.step_type = 'ADMIN' THEN 'ADMIN'
        WHEN refinement.code IN ('CARD-POST-PCI', 'ORTHO-TKA', 'ONCO-NEW', 'CHF-DISCHARGE')
          AND old_step.code IN ('CARD-FOLLOWUP', 'ORTHO-FOLLOWUP', 'ONCO-FOLLOWUP', 'HF-CLINIC') THEN 'CLINICIAN'
        WHEN refinement.code = 'ONCO-NEW' AND old_step.code = 'EDUCATION' THEN 'CLINICIAN'
        WHEN refinement.code = 'DIAB-ANNUAL' AND old_step.code = 'LIFESTYLE' THEN 'CLINICIAN'
        WHEN refinement.code = 'COPD-EXAC' AND old_step.code = 'ACTION-PLAN' THEN 'CLINICIAN'
        WHEN old_step.step_type IN ('EDUCATION', 'FOLLOWUP', 'APPOINTMENT', 'REFERRAL', 'COUNSELLING', 'THERAPY') THEN 'CARE_COORDINATOR'
        ELSE 'CLINICIAN'
    END,
    old_step.due_after_days,
    CASE
        WHEN old_step.code IN ('PHONE-72H', 'PHONE-30D') THEN 24
        WHEN old_step.code = 'AUTH' THEN 72
        WHEN old_step.step_type IN ('PROCEDURE', 'THERAPY') THEN 168
        WHEN old_step.step_type IN ('DISCHARGE') THEN 24
        WHEN old_step.step_type IN ('LAB', 'CLINICAL', 'SCREENING', 'PREVENTION') THEN 48
        WHEN old_step.step_type IN ('ADMIN', 'APPOINTMENT', 'FOLLOWUP', 'REFERRAL', 'EDUCATION', 'COUNSELLING', 'CLOSURE') THEN 72
        ELSE 48
    END,
    old_step.completion_criteria,
    now(),
    now()
FROM pathway_steps old_step
JOIN pathway_step_refinement_map step_map ON step_map.old_step_id = old_step.id
JOIN pathway_refinement_map refinement ON refinement.new_pathway_id = step_map.new_pathway_id;

WITH RECURSIVE ordered_steps AS (
    SELECT step.id, step.pathway_id, step.sequence_number,
           GREATEST(COALESCE(step.due_after_days, 0), 0) AS target_day
    FROM pathway_steps step
    JOIN pathway_refinement_map refinement ON refinement.new_pathway_id = step.pathway_id
    WHERE step.sequence_number = 1
    UNION ALL
    SELECT following.id, following.pathway_id, following.sequence_number,
           GREATEST(COALESCE(following.due_after_days, ordered_steps.target_day + 1), ordered_steps.target_day + 1)
    FROM ordered_steps
    JOIN pathway_steps following ON following.pathway_id = ordered_steps.pathway_id
      AND following.sequence_number = ordered_steps.sequence_number + 1
), milestones AS (
    SELECT id, target_day FROM ordered_steps
)
UPDATE pathway_steps step
SET due_after_days = milestones.target_day, updated_at = now()
FROM milestones
WHERE step.id = milestones.id;

INSERT INTO dependencies (
    id, pathway_id, source_step_id, target_step_id, condition_type,
    condition_config, blocking, created_at
)
SELECT
    (md5('dependency:workflow-refinement:' || dependency.id::text))::uuid,
    refinement.new_pathway_id,
    source_map.new_step_id,
    target_map.new_step_id,
    dependency.condition_type,
    dependency.condition_config,
    dependency.blocking,
    now()
FROM dependencies dependency
JOIN pathway_refinement_map refinement ON refinement.old_pathway_id = dependency.pathway_id
JOIN pathway_step_refinement_map source_map ON source_map.old_step_id = dependency.source_step_id
JOIN pathway_step_refinement_map target_map ON target_map.old_step_id = dependency.target_step_id;

INSERT INTO pathway_action_rules (
    id, pathway_step_id, action_type, enabled, requires_approval, conditions, created_at
)
SELECT
    (md5('pathway-action-rule:workflow-refinement:' || action_rule.id::text))::uuid,
    step_map.new_step_id,
    action_rule.action_type,
    action_rule.enabled,
    action_rule.requires_approval,
    action_rule.conditions,
    now()
FROM pathway_action_rules action_rule
JOIN pathway_step_refinement_map step_map ON step_map.old_step_id = action_rule.pathway_step_id;

COMMIT;
