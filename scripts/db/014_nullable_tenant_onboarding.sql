-- 014: Make tenant_id nullable in chat_sessions and quality_issues
-- Purpose: Support onboarding users who don't have a tenant yet.
-- Consistent with agent_interactions.tenant_id which is already nullable.

-- chat_sessions: drop FK constraint, make nullable
ALTER TABLE chat_sessions DROP CONSTRAINT IF EXISTS chat_sessions_tenant_id_fkey;
ALTER TABLE chat_sessions ALTER COLUMN tenant_id DROP NOT NULL;

-- quality_issues: drop FK constraint, make nullable
ALTER TABLE quality_issues DROP CONSTRAINT IF EXISTS quality_issues_tenant_id_fkey;
ALTER TABLE quality_issues ALTER COLUMN tenant_id DROP NOT NULL;
