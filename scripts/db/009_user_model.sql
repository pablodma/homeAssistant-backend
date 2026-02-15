-- Migration: 009_user_model.sql
-- Description: Refactor users as first-class entity. Migrate phone_tenant_mapping data into users.
-- Date: 2026-02-15
--
-- WHAT THIS DOES:
-- 1. Expands users table with profile fields (avatar, verification flags, etc.)
-- 2. Makes phone nullable (OAuth users don't need a phone)
-- 3. Migrates phone_tenant_mapping entries into users (one user per phone)
-- 4. Cleans up oauth: placeholder phones
-- 5. Deprecates phone_tenant_mapping (renamed, not dropped)
--
-- SAFE TO RE-RUN: All operations use IF NOT EXISTS / IF EXISTS guards.

-- ============================================================================
-- 1. Add new columns to users table
-- ============================================================================

ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_url VARCHAR(500);
ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified BOOLEAN DEFAULT false;
ALTER TABLE users ADD COLUMN IF NOT EXISTS phone_verified BOOLEAN DEFAULT false;
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMPTZ;
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT true;
ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

COMMENT ON COLUMN users.avatar_url IS 'Profile picture URL (from Google OAuth)';
COMMENT ON COLUMN users.email_verified IS 'Whether email was verified via OAuth';
COMMENT ON COLUMN users.phone_verified IS 'Whether phone was verified (WhatsApp interaction or code)';
COMMENT ON COLUMN users.last_login_at IS 'Last web login timestamp';
COMMENT ON COLUMN users.is_active IS 'Soft-delete flag';
COMMENT ON COLUMN users.updated_at IS 'Last profile update timestamp';

-- ============================================================================
-- 2. Make phone nullable and fix constraints
-- ============================================================================

-- Drop the old UNIQUE constraint on phone (it was created in init.sql as UNIQUE(phone))
-- The constraint name in PostgreSQL is typically "users_phone_key"
ALTER TABLE users DROP CONSTRAINT IF EXISTS users_phone_key;

-- Make phone nullable
ALTER TABLE users ALTER COLUMN phone DROP NOT NULL;

-- Clean up oauth: placeholder phones → set to NULL
UPDATE users SET phone = NULL WHERE phone LIKE 'oauth:%';

-- Add partial unique index: phone must be unique among non-null, real phones
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_phone_unique 
    ON users(phone) 
    WHERE phone IS NOT NULL;

-- Add index on email for OAuth lookups
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- ============================================================================
-- 3. Migrate phone_tenant_mapping data into users
-- ============================================================================
-- For each phone in phone_tenant_mapping that doesn't already have a user
-- record with that phone, create a new user.

INSERT INTO users (tenant_id, phone, email, display_name, role, phone_verified, is_active, auth_provider, created_at)
SELECT 
    ptm.tenant_id,
    ptm.phone,
    NULL,  -- no email for WhatsApp-only members
    ptm.display_name,
    CASE WHEN ptm.is_primary THEN 'admin' ELSE 'member' END,
    ptm.verified_at IS NOT NULL,  -- phone_verified = true if they had a verified_at
    true,  -- is_active
    'whatsapp',
    ptm.created_at
FROM phone_tenant_mapping ptm
WHERE NOT EXISTS (
    -- Skip if a user with this phone already exists
    SELECT 1 FROM users u WHERE u.phone = ptm.phone
)
AND ptm.user_id IS NULL;  -- Only migrate entries that weren't linked to a user

-- For entries that WERE linked to a user_id, update that user's phone if it's still null
UPDATE users u
SET 
    phone = ptm.phone,
    phone_verified = (ptm.verified_at IS NOT NULL),
    display_name = COALESCE(u.display_name, ptm.display_name)
FROM phone_tenant_mapping ptm
WHERE ptm.user_id = u.id
  AND (u.phone IS NULL OR u.phone LIKE 'oauth:%')
  AND ptm.phone IS NOT NULL;

-- ============================================================================
-- 4. Mark OAuth users with verified email
-- ============================================================================

UPDATE users 
SET email_verified = true
WHERE email IS NOT NULL 
  AND auth_provider = 'google';

-- ============================================================================
-- 5. Add updated_at trigger for users
-- ============================================================================

CREATE OR REPLACE FUNCTION update_users_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS update_users_updated_at ON users;
CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_users_updated_at();

-- ============================================================================
-- 6. Deprecate phone_tenant_mapping (rename, don't drop)
-- ============================================================================
-- Keeping the table renamed as backup. Can be dropped in a future migration.

ALTER TABLE IF EXISTS phone_tenant_mapping RENAME TO _deprecated_phone_tenant_mapping;

-- ============================================================================
-- 7. Update table comment
-- ============================================================================

COMMENT ON TABLE users IS 'Users (people) belonging to a tenant/account. Source of truth for membership, authentication, and bot phone resolution.';

-- ============================================================================
-- Done
-- ============================================================================
