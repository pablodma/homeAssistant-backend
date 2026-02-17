-- 016: Starter plan is no longer free - update price to $4.99/mes
-- This migration updates the Starter plan pricing from $0 (free) to $4.99

UPDATE plan_pricing 
SET price_monthly = 4.99,
    updated_at = NOW()
WHERE plan_type = 'starter';
