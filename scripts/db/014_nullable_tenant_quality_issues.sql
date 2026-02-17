-- =====================================================
-- 014: Make tenant_id nullable in quality_issues
-- =====================================================
-- Quality issues can reference interactions from
-- unregistered users (acquisition mode) where no
-- tenant exists yet.
-- =====================================================

ALTER TABLE quality_issues ALTER COLUMN tenant_id DROP NOT NULL;

COMMENT ON COLUMN quality_issues.tenant_id IS 'Tenant ID. NULL for issues from acquisition-mode interactions (unregistered users)';
