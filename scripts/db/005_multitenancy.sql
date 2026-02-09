-- Migration: 005_multitenancy.sql
-- Description: Enable dynamic multitenancy by creating phone-tenant mapping
-- Date: 2026-02-09

-- ============================================================================
-- 1. Create phone_tenant_mapping table
-- ============================================================================
-- Maps phone numbers to tenants for bot multitenancy resolution

CREATE TABLE IF NOT EXISTS phone_tenant_mapping (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phone VARCHAR(20) NOT NULL,              -- E.164 format: +5491112345678
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    is_primary BOOLEAN DEFAULT false,        -- True if this is the tenant owner
    display_name VARCHAR(100),               -- Name to use in bot responses
    verified_at TIMESTAMP WITH TIME ZONE,    -- When phone was verified
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT unique_phone UNIQUE (phone)
);

-- Indexes for efficient lookups
CREATE INDEX IF NOT EXISTS idx_phone_tenant_phone ON phone_tenant_mapping(phone);
CREATE INDEX IF NOT EXISTS idx_phone_tenant_tenant ON phone_tenant_mapping(tenant_id);
CREATE INDEX IF NOT EXISTS idx_phone_tenant_user ON phone_tenant_mapping(user_id);

COMMENT ON TABLE phone_tenant_mapping IS 'Maps WhatsApp phone numbers to tenants for multitenancy';
COMMENT ON COLUMN phone_tenant_mapping.phone IS 'Phone number in E.164 format';
COMMENT ON COLUMN phone_tenant_mapping.is_primary IS 'True if this phone is the tenant owner/creator';
COMMENT ON COLUMN phone_tenant_mapping.verified_at IS 'Timestamp when phone ownership was verified';

-- ============================================================================
-- 2. Extend tenants table for onboarding
-- ============================================================================

-- Add home_name column (friendly name for the household)
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS home_name VARCHAR(100);

-- Add plan column (starter, family, premium)
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS plan VARCHAR(20) DEFAULT 'starter';

-- Add owner reference
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS owner_user_id UUID REFERENCES users(id) ON DELETE SET NULL;

-- Add onboarding status
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS onboarding_completed BOOLEAN DEFAULT false;

-- Add timezone and locale settings
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS timezone VARCHAR(50) DEFAULT 'America/Argentina/Buenos_Aires';
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS language VARCHAR(10) DEFAULT 'es-AR';
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS currency VARCHAR(10) DEFAULT 'ARS';

-- Update existing tenant with defaults
UPDATE tenants 
SET 
    home_name = COALESCE(home_name, name),
    onboarding_completed = true  -- Existing tenant is already set up
WHERE id = '00000000-0000-0000-0000-000000000001';

COMMENT ON COLUMN tenants.home_name IS 'Friendly name for the household (e.g., "Casa de Pablo")';
COMMENT ON COLUMN tenants.plan IS 'Subscription plan: starter, family, premium';
COMMENT ON COLUMN tenants.owner_user_id IS 'User who created/owns this tenant';
COMMENT ON COLUMN tenants.onboarding_completed IS 'Whether initial setup is complete';

-- ============================================================================
-- 3. Add tenant_id to users for OAuth users without phone
-- ============================================================================
-- Note: users.tenant_id already exists, but we need to handle the case where
-- a user might not have a real phone (OAuth users use oauth:email placeholder)

-- Add a flag to distinguish OAuth vs WhatsApp users
ALTER TABLE users ADD COLUMN IF NOT EXISTS auth_provider VARCHAR(20) DEFAULT 'whatsapp';

UPDATE users 
SET auth_provider = 'google'
WHERE phone LIKE 'oauth:%';

COMMENT ON COLUMN users.auth_provider IS 'Authentication provider: google, whatsapp';

-- ============================================================================
-- 4. Trigger for updated_at
-- ============================================================================

CREATE OR REPLACE FUNCTION update_phone_tenant_mapping_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS update_phone_tenant_mapping_updated_at ON phone_tenant_mapping;
CREATE TRIGGER update_phone_tenant_mapping_updated_at
    BEFORE UPDATE ON phone_tenant_mapping
    FOR EACH ROW
    EXECUTE FUNCTION update_phone_tenant_mapping_updated_at();

-- ============================================================================
-- 5. Migration data: Map existing users to phone_tenant_mapping
-- ============================================================================
-- This migrates existing WhatsApp users to the new mapping table

INSERT INTO phone_tenant_mapping (phone, tenant_id, user_id, is_primary, display_name, verified_at)
SELECT 
    u.phone,
    u.tenant_id,
    u.id,
    (u.role = 'owner' OR u.role = 'admin'),
    u.display_name,
    NOW()
FROM users u
WHERE u.phone NOT LIKE 'oauth:%'  -- Exclude OAuth placeholder phones
  AND u.phone IS NOT NULL
  AND u.phone != ''
ON CONFLICT (phone) DO NOTHING;

-- ============================================================================
-- Done
-- ============================================================================
