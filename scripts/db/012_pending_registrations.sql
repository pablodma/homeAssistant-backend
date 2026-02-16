-- Migration 012: Pending registrations for WhatsApp onboarding
-- 
-- Stores registration data for users who choose a paid plan via WhatsApp.
-- The bot collects name/home_name, creates a pending record, generates
-- a Lemon Squeezy checkout link, and waits for the webhook to confirm payment.
-- On payment confirmation, the LS webhook handler creates the tenant from this data.

CREATE TABLE IF NOT EXISTS pending_registrations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phone VARCHAR(20) NOT NULL,
    display_name VARCHAR(100) NOT NULL,
    home_name VARCHAR(100) NOT NULL,
    plan_type VARCHAR(20) NOT NULL,
    coupon_code VARCHAR(50),
    ls_checkout_id VARCHAR(100),
    status VARCHAR(20) NOT NULL DEFAULT 'pending',  -- pending, completed, expired
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL DEFAULT NOW() + INTERVAL '24 hours'
);

CREATE INDEX IF NOT EXISTS idx_pending_registrations_phone 
    ON pending_registrations(phone) WHERE status = 'pending';

CREATE INDEX IF NOT EXISTS idx_pending_registrations_ls_checkout 
    ON pending_registrations(ls_checkout_id) WHERE ls_checkout_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_pending_registrations_status 
    ON pending_registrations(status, expires_at);

COMMENT ON TABLE pending_registrations IS 
    'Stores pre-payment registration data collected via WhatsApp onboarding. '
    'Completed when LS webhook confirms payment, expired after 24h.';
