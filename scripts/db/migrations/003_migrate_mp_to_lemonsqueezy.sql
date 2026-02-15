-- Migration: Replace Mercado Pago columns with Lemon Squeezy columns
-- Date: 2026-02-12
-- Description: Migrates subscriptions and payments tables from MP to LS

BEGIN;

-- =============================================================================
-- 1. Subscriptions table: Replace MP columns with LS columns
-- =============================================================================

-- Add new LS columns
ALTER TABLE subscriptions
    ADD COLUMN IF NOT EXISTS ls_subscription_id TEXT,
    ADD COLUMN IF NOT EXISTS ls_checkout_id TEXT;

-- Drop old MP columns (after verifying no critical data)
ALTER TABLE subscriptions
    DROP COLUMN IF EXISTS mp_preapproval_id,
    DROP COLUMN IF EXISTS mp_payer_id;

-- Create index for LS subscription lookups
CREATE INDEX IF NOT EXISTS idx_subscriptions_ls_subscription_id
    ON subscriptions (ls_subscription_id)
    WHERE ls_subscription_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_subscriptions_ls_checkout_id
    ON subscriptions (ls_checkout_id)
    WHERE ls_checkout_id IS NOT NULL;

-- =============================================================================
-- 2. Subscription payments: Replace MP columns with LS columns
-- =============================================================================

-- Add new LS column
ALTER TABLE subscription_payments
    ADD COLUMN IF NOT EXISTS ls_invoice_id TEXT;

-- Drop old MP column
ALTER TABLE subscription_payments
    DROP COLUMN IF EXISTS mp_payment_id;

-- Update default currency from ARS to USD
ALTER TABLE subscription_payments
    ALTER COLUMN currency SET DEFAULT 'USD';

-- Create index for LS invoice lookups
CREATE INDEX IF NOT EXISTS idx_subscription_payments_ls_invoice_id
    ON subscription_payments (ls_invoice_id)
    WHERE ls_invoice_id IS NOT NULL;

-- =============================================================================
-- 3. Drop subscription_plans_mp table (no longer needed)
-- =============================================================================

DROP TABLE IF EXISTS subscription_plans_mp;

COMMIT;
