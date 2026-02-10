-- HomeAI Assistant - Plan Services Configurator
-- Version: 008
-- Fecha: 2026-02-08
-- Descripcion: Columna enabled_services para configurar que servicios tiene cada plan

-- =============================================================================
-- ENABLED SERVICES en plan_pricing
-- =============================================================================

ALTER TABLE plan_pricing ADD COLUMN IF NOT EXISTS enabled_services JSONB DEFAULT '[]'::jsonb;

COMMENT ON COLUMN plan_pricing.enabled_services IS 'IDs de servicios habilitados: reminder, shopping, finance, calendar, vehicle';

-- Datos iniciales segun configuracion actual de planes
UPDATE plan_pricing SET enabled_services = '["reminder","shopping"]'::jsonb WHERE plan_type = 'starter';
UPDATE plan_pricing SET enabled_services = '["reminder","shopping","finance","calendar","vehicle"]'::jsonb WHERE plan_type = 'family';
UPDATE plan_pricing SET enabled_services = '["reminder","shopping","finance","calendar","vehicle"]'::jsonb WHERE plan_type = 'premium';
