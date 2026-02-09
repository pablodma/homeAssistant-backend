-- Migration: Add chat memory and pending contexts tables
-- Version: 002
-- Date: 2026-02-09

-- =============================================================================
-- CHAT MEMORY (Agent Sessions)
-- =============================================================================

CREATE TABLE IF NOT EXISTS chat_sessions (
    session_key VARCHAR(255) PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    phone VARCHAR(20) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_sessions_tenant ON chat_sessions(tenant_id);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_phone ON chat_sessions(phone);

CREATE TABLE IF NOT EXISTS chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_key VARCHAR(255) NOT NULL REFERENCES chat_sessions(session_key) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON chat_messages(session_key, created_at);

-- =============================================================================
-- PENDING CONTEXTS (for interactive messages)
-- =============================================================================

CREATE TABLE IF NOT EXISTS pending_contexts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_key VARCHAR(255) NOT NULL,
    context_type VARCHAR(50) NOT NULL,
    context_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(session_key, context_type)
);

CREATE INDEX IF NOT EXISTS idx_pending_context_session ON pending_contexts(session_key);

-- =============================================================================
-- TRIGGERS
-- =============================================================================

-- Drop triggers if they exist (to make migration idempotent)
DROP TRIGGER IF EXISTS update_chat_sessions_updated_at ON chat_sessions;
DROP TRIGGER IF EXISTS update_pending_contexts_updated_at ON pending_contexts;

-- Create triggers
CREATE TRIGGER update_chat_sessions_updated_at BEFORE UPDATE ON chat_sessions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_pending_contexts_updated_at BEFORE UPDATE ON pending_contexts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
