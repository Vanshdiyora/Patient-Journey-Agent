-- Refresh synthetic pathway timing after clinical_seed_updates.sql.
-- Only numeric PT-2026 demo patients are changed; manually created patients are excluded.

-- A milestone is a day measured from journey start. Keep steps in chronological
-- order, including templates that originally had two milestones on one day.
WITH RECURSIVE ordered AS (
    SELECT ps.id, ps.pathway_id, ps.sequence_number,
           GREATEST(COALESCE(ps.due_after_days, 0), 0) AS target_day
    FROM pathway_steps ps
    JOIN pathways p ON p.id = ps.pathway_id
    WHERE ps.sequence_number = 1 AND p.status = 'ACTIVE' AND p.code IN (
        'CARD-POST-PCI', 'ORTHO-TKA', 'ONCO-NEW',
        'DIAB-ANNUAL', 'CHF-DISCHARGE', 'COPD-EXAC'
    )
    UNION ALL
    SELECT following.id, following.pathway_id, following.sequence_number,
           GREATEST(COALESCE(following.due_after_days, ordered.target_day + 1), ordered.target_day + 1)
    FROM ordered
    JOIN pathway_steps following ON following.pathway_id = ordered.pathway_id
      AND following.sequence_number = ordered.sequence_number + 1
), schedule AS (
    SELECT *, LAG(target_day, 1, 0) OVER (PARTITION BY pathway_id ORDER BY sequence_number) AS previous_day
    FROM ordered
)
UPDATE pathway_steps ps SET
    due_after_days = schedule.target_day,
    time_limit_hours = CASE
        WHEN ps.code IN ('PHONE-72H', 'PHONE-30D') THEN 24
        WHEN ps.code = 'AUTH' THEN 72
        WHEN ps.step_type IN ('PROCEDURE', 'THERAPY') THEN 168
        WHEN ps.step_type = 'DISCHARGE' THEN 24
        WHEN ps.step_type IN ('LAB', 'CLINICAL', 'SCREENING', 'PREVENTION') THEN 48
        WHEN ps.step_type IN ('ADMIN', 'APPOINTMENT', 'FOLLOWUP', 'REFERRAL', 'EDUCATION', 'COUNSELLING', 'CLOSURE') THEN 72
        ELSE 48
    END
FROM schedule WHERE ps.id = schedule.id;

UPDATE journey_steps js SET
    owner_role = active_step.owner_role,
    time_limit_hours = active_step.time_limit_hours
FROM pathway_steps source_step
JOIN pathways source_pathway ON source_pathway.id = source_step.pathway_id
JOIN pathways active_pathway ON active_pathway.code = source_pathway.code AND active_pathway.status = 'ACTIVE'
JOIN pathway_steps active_step ON active_step.pathway_id = active_pathway.id AND active_step.code = source_step.code
JOIN journeys j ON j.pathway_id = source_pathway.id
JOIN patients p ON p.id = j.patient_id
WHERE js.pathway_step_id = source_step.id
  AND js.journey_id = j.id
  AND p.patient_reference ~ '^PT-2026-[0-9]{6}$';

UPDATE journeys j SET
    started_at = CASE WHEN j.status = 'COMPLETED'
        THEN now() - ((SELECT max(ps.due_after_days) + 2 FROM pathway_steps ps WHERE ps.pathway_id = j.pathway_id) * interval '1 day')
        ELSE now() - ((10 + substring(p.patient_reference FROM '[0-9]+$')::integer % 20) * interval '1 day')
    END,
    completed_at = CASE WHEN j.status = 'COMPLETED' THEN now() - interval '1 day' ELSE NULL END,
    updated_at = now()
FROM patients p
WHERE j.patient_id = p.id AND p.patient_reference ~ '^PT-2026-[0-9]{6}$';

UPDATE journeys j SET target_completion_at = j.started_at + (
    SELECT max(ps.due_after_days) * interval '1 day'
    FROM pathway_steps ps WHERE ps.pathway_id = j.pathway_id
)
FROM patients p
WHERE j.patient_id = p.id AND p.patient_reference ~ '^PT-2026-[0-9]{6}$';

WITH stage AS (
    SELECT js.id, j.id AS journey_id, j.status AS journey_status,
           j.started_at AS journey_started_at, ps.sequence_number,
           ps.due_after_days AS target_day, js.time_limit_hours AS allowance_hours,
           floor(extract(epoch FROM (now() - j.started_at)) / 86400)::integer AS elapsed_days
    FROM journey_steps js
    JOIN journeys j ON j.id = js.journey_id
    JOIN patients p ON p.id = j.patient_id
    JOIN pathway_steps ps ON ps.id = js.pathway_step_id
    WHERE p.patient_reference ~ '^PT-2026-[0-9]{6}$'
), position AS (
    SELECT stage.*,
           COALESCE(
               min(sequence_number) FILTER (WHERE target_day >= elapsed_days - 1) OVER (PARTITION BY journey_id),
               max(sequence_number) OVER (PARTITION BY journey_id)
           ) AS current_sequence
    FROM stage
), resolved AS (
    SELECT position.*,
           CASE
               WHEN journey_status = 'COMPLETED' THEN 'COMPLETED'
               WHEN sequence_number < current_sequence THEN 'COMPLETED'
               WHEN journey_status = 'CANCELLED' THEN 'CANCELLED'
               WHEN sequence_number = current_sequence AND journey_status = 'BLOCKED' THEN 'BLOCKED'
               WHEN sequence_number = current_sequence THEN 'READY'
               ELSE 'PENDING'
           END AS next_status
    FROM position
)
UPDATE journey_steps js SET
    status = resolved.next_status::journey_step_status,
    started_at = CASE WHEN resolved.next_status IN ('COMPLETED', 'READY', 'BLOCKED')
        THEN resolved.journey_started_at
             + GREATEST(resolved.target_day - CEIL(resolved.allowance_hours / 24.0)::integer, 0) * interval '1 day'
        ELSE NULL END,
    completed_at = CASE WHEN resolved.next_status = 'COMPLETED'
        THEN resolved.journey_started_at + resolved.target_day * interval '1 day'
        ELSE NULL END,
    due_at = CASE WHEN resolved.next_status IN ('COMPLETED', 'READY', 'BLOCKED')
        THEN resolved.journey_started_at + resolved.target_day * interval '1 day'
        ELSE NULL END,
    block_reason = CASE WHEN resolved.next_status = 'BLOCKED' THEN 'Care team review required' ELSE NULL END,
    updated_at = now()
FROM resolved WHERE js.id = resolved.id;
