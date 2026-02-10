-- HomeAI - Reset OAuth Users (para testing)
-- Elimina usuarios OAuth (Google) y sus tenants para volver a probar el onboarding
-- Ejecutar con: psql $DATABASE_URL -f scripts/db/reset_oauth_users.sql

-- 1. Liberar referencias FK (omitir si las tablas no existen)
DO $$
BEGIN
  UPDATE plan_pricing SET updated_by = NULL
  WHERE updated_by IN (SELECT id FROM users WHERE auth_provider = 'google' AND phone LIKE 'oauth:%');
EXCEPTION WHEN undefined_table THEN NULL;
END $$;

DO $$
BEGIN
  UPDATE coupons SET created_by = NULL
  WHERE created_by IN (SELECT id FROM users WHERE auth_provider = 'google' AND phone LIKE 'oauth:%');
EXCEPTION WHEN undefined_table THEN NULL;
END $$;

-- 2. Eliminar tenants y users OAuth
BEGIN;

UPDATE tenants t
SET owner_user_id = NULL
FROM users u
WHERE t.owner_user_id = u.id
  AND u.auth_provider = 'google'
  AND u.phone LIKE 'oauth:%';

DELETE FROM tenants
WHERE id IN (
  SELECT tenant_id FROM users
  WHERE auth_provider = 'google'
    AND phone LIKE 'oauth:%'
    AND tenant_id != '00000000-0000-0000-0000-000000000001'
);

COMMIT;
