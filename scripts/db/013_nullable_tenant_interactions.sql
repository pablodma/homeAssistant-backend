-- =====================================================
-- 013: Make tenant_id nullable in agent_interactions
-- =====================================================
-- Allows logging interactions from unregistered users
-- (subscription agent in acquisition mode) where no
-- tenant exists yet.
-- =====================================================

ALTER TABLE agent_interactions ALTER COLUMN tenant_id DROP NOT NULL;

COMMENT ON COLUMN agent_interactions.tenant_id IS 'Tenant ID. NULL for acquisition-mode interactions (unregistered users)';
