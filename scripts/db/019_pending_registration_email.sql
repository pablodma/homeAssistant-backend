-- Migration 019: Add email column to pending_registrations
--
-- The email is collected during WhatsApp onboarding before checkout.
-- It is used for Lemon Squeezy invoicing and pre-fills the checkout form.

ALTER TABLE pending_registrations
    ADD COLUMN IF NOT EXISTS email VARCHAR(255);
