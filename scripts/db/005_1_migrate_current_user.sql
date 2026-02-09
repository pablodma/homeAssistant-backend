-- Migration: 005_1_migrate_current_user.sql
-- Description: Migrate existing user to the new multitenancy system
-- Date: 2026-02-09
-- 
-- IMPORTANT: Run this AFTER 005_multitenancy.sql
-- IMPORTANT: Replace YOUR_PHONE_NUMBER with your actual WhatsApp number in E.164 format
--            Example: +5491112345678

-- ============================================================================
-- 1. Set existing tenant as onboarding completed
-- ============================================================================

UPDATE tenants 
SET 
    home_name = COALESCE(home_name, 'Mi Hogar'),
    onboarding_completed = true,
    plan = 'family'
WHERE id = '00000000-0000-0000-0000-000000000001';

-- ============================================================================
-- 2. Update existing user as owner of the tenant
-- ============================================================================

-- First, get the user ID for the existing tenant
DO $$
DECLARE
    v_user_id UUID;
    v_tenant_id UUID := '00000000-0000-0000-0000-000000000001';
BEGIN
    -- Get the first user in the tenant (should be the owner)
    SELECT id INTO v_user_id 
    FROM users 
    WHERE tenant_id = v_tenant_id 
    ORDER BY created_at ASC 
    LIMIT 1;
    
    IF v_user_id IS NOT NULL THEN
        -- Update user to be owner
        UPDATE users 
        SET role = 'owner', auth_provider = COALESCE(auth_provider, 'google')
        WHERE id = v_user_id;
        
        -- Set owner on tenant
        UPDATE tenants 
        SET owner_user_id = v_user_id 
        WHERE id = v_tenant_id;
        
        RAISE NOTICE 'Updated user % as owner of tenant %', v_user_id, v_tenant_id;
    ELSE
        RAISE WARNING 'No users found for tenant %', v_tenant_id;
    END IF;
END $$;

-- ============================================================================
-- 3. Register your WhatsApp phone number
-- ============================================================================
-- 
-- INSTRUCTIONS: 
-- 1. Replace 'YOUR_PHONE_NUMBER' with your actual WhatsApp number
-- 2. The format must be E.164: +CountryCode followed by number
--    Examples: +5491112345678 (Argentina), +34612345678 (Spain)
--
-- Uncomment and modify the following line:
--
-- INSERT INTO phone_tenant_mapping (phone, tenant_id, display_name, is_primary, verified_at)
-- VALUES (
--     '+YOUR_PHONE_NUMBER',  -- Replace with your WhatsApp number
--     '00000000-0000-0000-0000-000000000001',
--     'Pablo',  -- Replace with your name
--     true,
--     NOW()
-- )
-- ON CONFLICT (phone) DO NOTHING;

-- ============================================================================
-- Verification queries (run to check the migration worked)
-- ============================================================================

-- Check tenant:
-- SELECT id, name, home_name, plan, onboarding_completed, owner_user_id FROM tenants;

-- Check users:
-- SELECT id, email, role, auth_provider, tenant_id FROM users;

-- Check phone mappings:
-- SELECT * FROM phone_tenant_mapping;
