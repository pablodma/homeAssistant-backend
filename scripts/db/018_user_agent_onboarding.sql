-- 018: User Agent Onboarding tracking
-- Tracks first-time use per user per agent for guided setup

CREATE TABLE IF NOT EXISTS user_agent_onboarding (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    agent_name VARCHAR(50) NOT NULL,
    completed BOOLEAN NOT NULL DEFAULT false,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, agent_name)
);

CREATE INDEX IF NOT EXISTS idx_user_agent_onboarding_user ON user_agent_onboarding(user_id);
CREATE INDEX IF NOT EXISTS idx_user_agent_onboarding_lookup ON user_agent_onboarding(user_id, agent_name);
