-- 010: Add admin_insight column to quality_issues
-- Allows platform admins to annotate quality issues with their own analysis,
-- which feeds into the continuous improvement pipeline.

ALTER TABLE quality_issues ADD COLUMN IF NOT EXISTS admin_insight TEXT;

COMMENT ON COLUMN quality_issues.admin_insight IS 'Admin-provided insight that influences prompt improvement generation';
