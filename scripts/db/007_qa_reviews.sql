-- Migration: QA Review Cycles and Prompt Revisions
-- Description: Tables for tracking automated QA reviews and prompt improvements
-- Date: 2026-02-12

-- =====================================================
-- QA REVIEW CYCLES
-- Tracks each execution of the QA batch review process
-- =====================================================

CREATE TABLE IF NOT EXISTS qa_review_cycles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,

    -- Who triggered it
    triggered_by VARCHAR(200) NOT NULL,  -- email of the admin who clicked the button

    -- Analysis window
    period_start TIMESTAMPTZ NOT NULL,   -- start of the issues window analyzed
    period_end TIMESTAMPTZ NOT NULL,     -- end of the issues window analyzed

    -- Results
    issues_analyzed_count INT NOT NULL DEFAULT 0,
    improvements_applied_count INT NOT NULL DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'running',  -- 'running', 'completed', 'failed'
    error_message TEXT,                  -- error details if status = 'failed'

    -- Full analysis result from Claude (parsed XML sections)
    analysis_result JSONB,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_qa_review_cycles_tenant
ON qa_review_cycles(tenant_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_qa_review_cycles_status
ON qa_review_cycles(tenant_id, status);

-- Comments
COMMENT ON TABLE qa_review_cycles IS 'Tracks each execution of the QA batch review (on-demand from admin panel)';
COMMENT ON COLUMN qa_review_cycles.triggered_by IS 'Email of the admin who triggered the review';
COMMENT ON COLUMN qa_review_cycles.analysis_result IS 'Parsed Claude response: understanding_errors, hard_errors, improvement_proposals, summary';
COMMENT ON COLUMN qa_review_cycles.status IS 'running = in progress, completed = finished, failed = error occurred';


-- =====================================================
-- PROMPT REVISIONS
-- Tracks each automatic change to an agent prompt
-- =====================================================

CREATE TABLE IF NOT EXISTS prompt_revisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    review_cycle_id UUID NOT NULL REFERENCES qa_review_cycles(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,

    -- Which agent was modified
    agent_name VARCHAR(50) NOT NULL,

    -- Before / After
    original_prompt TEXT NOT NULL,
    improved_prompt TEXT NOT NULL,

    -- Why it was changed
    improvement_reason TEXT NOT NULL,         -- Claude's explanation
    changes_summary JSONB,                    -- structured list of changes
    issues_addressed JSONB,                   -- array of quality_issue IDs that motivated this

    -- GitHub commit info
    github_commit_sha VARCHAR(50),
    github_commit_url TEXT,

    -- Rollback tracking
    is_rolled_back BOOLEAN DEFAULT false,
    rolled_back_at TIMESTAMPTZ,
    rolled_back_by VARCHAR(200),
    rollback_commit_sha VARCHAR(50),
    rollback_commit_url TEXT,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_prompt_revisions_cycle
ON prompt_revisions(review_cycle_id);

CREATE INDEX IF NOT EXISTS idx_prompt_revisions_tenant_agent
ON prompt_revisions(tenant_id, agent_name, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_prompt_revisions_not_rolled_back
ON prompt_revisions(tenant_id, agent_name)
WHERE is_rolled_back = false;

-- Comments
COMMENT ON TABLE prompt_revisions IS 'History of automatic prompt improvements made by the QA Reviewer';
COMMENT ON COLUMN prompt_revisions.original_prompt IS 'Full prompt content before modification';
COMMENT ON COLUMN prompt_revisions.improved_prompt IS 'Full prompt content after modification';
COMMENT ON COLUMN prompt_revisions.improvement_reason IS 'Claude explanation of why this change was made';
COMMENT ON COLUMN prompt_revisions.changes_summary IS 'JSON array of {section, change, reason} for each modification';
COMMENT ON COLUMN prompt_revisions.issues_addressed IS 'JSON array of quality_issue UUIDs that motivated this change';
