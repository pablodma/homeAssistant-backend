-- 015: Restructure onboarding flow — home_name moves to post-payment setup
-- All plans (including Starter) now go through Lemon Squeezy checkout.
-- home_name is collected AFTER payment, not before.

ALTER TABLE pending_registrations ALTER COLUMN home_name DROP NOT NULL;
ALTER TABLE pending_registrations ALTER COLUMN home_name SET DEFAULT NULL;
