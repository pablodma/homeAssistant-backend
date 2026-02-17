-- Migration: Fix shopping_items schema mismatch
-- Description: Drop old shopping_items/shopping_lists (init.sql schema) and recreate
--              with the correct schema expected by the shopping agent (003_agent_admin.sql schema).
--              The init.sql schema used list_id FK + name + purchased columns,
--              but the agent code expects list_name + item_name + is_purchased + user_phone.
-- Date: 2026-02-17

-- Drop old tables (shopping_items depends on shopping_lists via FK in init.sql schema)
DROP TABLE IF EXISTS shopping_items CASCADE;
DROP TABLE IF EXISTS shopping_lists CASCADE;

-- Recreate shopping_items with the correct schema (matches agent code)
CREATE TABLE shopping_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_phone VARCHAR(20) NOT NULL,
    list_name VARCHAR(100) DEFAULT 'Supermercado',
    item_name VARCHAR(200) NOT NULL,
    quantity DECIMAL(10,2) DEFAULT 1,
    unit VARCHAR(20),
    is_purchased BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_shopping_tenant ON shopping_items(tenant_id, list_name);
CREATE INDEX idx_shopping_user ON shopping_items(tenant_id, user_phone);
CREATE INDEX idx_shopping_not_purchased ON shopping_items(tenant_id, list_name) WHERE is_purchased = false;

COMMENT ON TABLE shopping_items IS 'Shopping list items managed by the shopping agent';

-- RLS policy
ALTER TABLE shopping_items ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_shopping_items ON shopping_items
    USING (tenant_id = current_setting('app.current_tenant')::uuid);
