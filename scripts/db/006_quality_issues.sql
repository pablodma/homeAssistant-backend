-- Migration: Quality Issues Table
-- Description: Table for storing hard errors and soft errors (QA Agent findings)
-- Date: 2026-02-09

-- =====================================================
-- QUALITY ISSUES TABLE
-- Stores both hard errors (technical) and soft errors (QA detected)
-- =====================================================

CREATE TABLE IF NOT EXISTS quality_issues (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    interaction_id UUID REFERENCES agent_interactions(id) ON DELETE SET NULL,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    
    -- Classification
    issue_type VARCHAR(20) NOT NULL,  -- 'hard_error', 'soft_error'
    issue_category VARCHAR(50) NOT NULL,
    -- Hard error categories: 'api_error', 'llm_error', 'timeout', 'database_error', 'webhook_error'
    -- Soft error categories: 'misinterpretation', 'hallucination', 'unsupported_case', 'incomplete_response'
    
    -- Context
    user_phone VARCHAR(100),
    agent_name VARCHAR(50),
    tool_name VARCHAR(100),
    message_in TEXT,
    message_out TEXT,
    
    -- Error details
    error_code VARCHAR(50),
    error_message TEXT NOT NULL,
    severity VARCHAR(20) DEFAULT 'medium',  -- 'low', 'medium', 'high', 'critical'
    
    -- QA Agent analysis (for soft errors)
    qa_analysis TEXT,           -- Explanation of the detected problem
    qa_suggestion TEXT,         -- Suggested improvement
    qa_confidence DECIMAL(3,2), -- 0.00-1.00 confidence score
    
    -- Metadata
    request_payload JSONB,
    stack_trace TEXT,
    correlation_id VARCHAR(50),  -- For linking with Railway logs
    
    -- Resolution tracking
    is_resolved BOOLEAN DEFAULT false,
    resolved_at TIMESTAMPTZ,
    resolved_by VARCHAR(100),
    resolution_notes TEXT,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_quality_issues_tenant_date 
ON quality_issues(tenant_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_quality_issues_type 
ON quality_issues(tenant_id, issue_type);

CREATE INDEX IF NOT EXISTS idx_quality_issues_category 
ON quality_issues(tenant_id, issue_category);

CREATE INDEX IF NOT EXISTS idx_quality_issues_unresolved 
ON quality_issues(tenant_id, is_resolved) 
WHERE is_resolved = false;

CREATE INDEX IF NOT EXISTS idx_quality_issues_severity 
ON quality_issues(tenant_id, severity) 
WHERE is_resolved = false;

CREATE INDEX IF NOT EXISTS idx_quality_issues_agent 
ON quality_issues(tenant_id, agent_name);

-- Comments
COMMENT ON TABLE quality_issues IS 'Stores hard errors (technical) and soft errors (QA Agent findings) for continuous improvement';
COMMENT ON COLUMN quality_issues.issue_type IS 'hard_error = technical exception, soft_error = QA detected quality issue';
COMMENT ON COLUMN quality_issues.issue_category IS 'Specific category: api_error, llm_error, timeout, misinterpretation, hallucination, etc.';
COMMENT ON COLUMN quality_issues.severity IS 'Impact level: low, medium, high, critical';
COMMENT ON COLUMN quality_issues.qa_analysis IS 'LLM explanation of why this is a quality issue (soft errors only)';
COMMENT ON COLUMN quality_issues.qa_suggestion IS 'LLM suggested fix or improvement (soft errors only)';
COMMENT ON COLUMN quality_issues.qa_confidence IS 'LLM confidence in the analysis (0.00-1.00)';
COMMENT ON COLUMN quality_issues.correlation_id IS 'UUID to correlate with Railway structured logs';
