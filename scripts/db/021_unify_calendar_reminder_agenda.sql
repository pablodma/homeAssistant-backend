-- Migration 021: Unify Calendar + Reminder agents into Agenda
-- Merges user_agent_onboarding records so existing users don't see first-time flow again
-- Updates plan_pricing.enabled_services JSONB to replace calendar/reminder with agenda

BEGIN;

-- 1. Merge calendar and reminder onboarding records into agenda
UPDATE user_agent_onboarding
SET agent_name = 'agenda'
WHERE agent_name IN ('calendar', 'reminder');

-- Remove duplicates: if a user now has two 'agenda' rows, keep one
DELETE FROM user_agent_onboarding
WHERE id NOT IN (
    SELECT DISTINCT ON (user_id, agent_name) id
    FROM user_agent_onboarding
    WHERE agent_name = 'agenda'
    ORDER BY user_id, agent_name, completed_at DESC NULLS LAST
)
AND agent_name = 'agenda';

-- 2. Update plan_pricing.enabled_services JSONB
-- Replace "calendar" and "reminder" with "agenda" in all plans
UPDATE plan_pricing
SET enabled_services = (
    SELECT jsonb_agg(DISTINCT val)
    FROM (
        SELECT
            CASE
                WHEN val::text IN ('"calendar"', '"reminder"') THEN '"agenda"'::jsonb
                ELSE val
            END AS val
        FROM jsonb_array_elements(enabled_services) AS val
    ) sub
)
WHERE enabled_services IS NOT NULL
  AND (enabled_services @> '"calendar"' OR enabled_services @> '"reminder"');

-- Update comment
COMMENT ON COLUMN plan_pricing.enabled_services IS 'IDs de servicios habilitados: agenda, shopping, finance, vehicle';

COMMIT;
