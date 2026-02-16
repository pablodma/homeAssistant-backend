-- 011: Add fix_status tracking columns to quality_issues
-- Enables async fix processing with status tracking in the admin panel.
-- States: null (no fix), in_progress, completed, failed

ALTER TABLE quality_issues ADD COLUMN IF NOT EXISTS fix_status TEXT;
ALTER TABLE quality_issues ADD COLUMN IF NOT EXISTS fix_error TEXT;
ALTER TABLE quality_issues ADD COLUMN IF NOT EXISTS fix_result JSONB;

COMMENT ON COLUMN quality_issues.fix_status IS 'Fix processing status: null, in_progress, completed, failed';
COMMENT ON COLUMN quality_issues.fix_error IS 'Error message when fix_status is failed';
COMMENT ON COLUMN quality_issues.fix_result IS 'Fix result data (revision_id, commit info, etc.) when completed';
