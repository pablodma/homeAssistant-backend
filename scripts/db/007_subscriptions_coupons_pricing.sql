-- HomeAI Assistant - Subscriptions, Coupons & Pricing Migration
-- Version: 007
-- Fecha: 2026-02-08
-- Descripcion: Tablas para suscripciones con Mercado Pago, cupones de descuento y precios de planes

-- =============================================================================
-- PLAN PRICING (Configuracion de planes editable desde admin)
-- =============================================================================

CREATE TABLE plan_pricing (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_type VARCHAR(20) UNIQUE NOT NULL, -- 'starter', 'family', 'premium'
    name VARCHAR(100) NOT NULL,
    description VARCHAR(255),
    price_monthly DECIMAL(10,2) NOT NULL, -- 0 para starter
    currency VARCHAR(3) DEFAULT 'ARS',
    max_members INTEGER NOT NULL,
    max_messages_month INTEGER, -- NULL = ilimitado
    history_days INTEGER NOT NULL,
    features JSONB DEFAULT '[]'::jsonb, -- Lista de features para mostrar
    active BOOLEAN DEFAULT true,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    updated_by UUID REFERENCES users(id),
    CONSTRAINT valid_plan_type CHECK (plan_type IN ('starter', 'family', 'premium')),
    CONSTRAINT positive_price CHECK (price_monthly >= 0),
    CONSTRAINT positive_members CHECK (max_members > 0),
    CONSTRAINT positive_history CHECK (history_days > 0)
);

CREATE INDEX idx_plan_pricing_type ON plan_pricing(plan_type);

COMMENT ON TABLE plan_pricing IS 'Configuracion de planes con precios editables desde admin';
COMMENT ON COLUMN plan_pricing.features IS 'Lista de features en formato JSON para mostrar en pricing page';

-- Datos iniciales de planes
INSERT INTO plan_pricing (plan_type, name, description, price_monthly, max_members, max_messages_month, history_days, features) VALUES
('starter', 'Starter', 'Perfecto para empezar a organizar tu hogar', 0, 2, 50, 7, 
 '["2 miembros del hogar", "2 agentes (Recordatorios + Listas)", "50 mensajes WhatsApp/mes", "Historial de 7 días", "Soporte comunidad"]'::jsonb),
('family', 'Family', 'Para familias que quieren todo bajo control', 9.99, 5, 500, 30,
 '["5 miembros del hogar", "5 agentes (Todos)", "500 mensajes WhatsApp/mes", "Historial de 30 días", "Soporte por email", "Presupuesto y Gastos", "Calendario", "Gestión de Vehículos"]'::jsonb),
('premium', 'Premium', 'Máxima flexibilidad para hogares grandes', 19.99, 999, NULL, 365,
 '["Miembros ilimitados", "5 agentes + Prioridad", "Mensajes WhatsApp ilimitados", "Historial de 1 año", "Soporte prioritario", "Presupuesto y Gastos", "Calendario", "Gestión de Vehículos"]'::jsonb);

-- =============================================================================
-- SUBSCRIPTION PLANS MP (Cache/sync con Mercado Pago)
-- =============================================================================

CREATE TABLE subscription_plans_mp (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_pricing_id UUID NOT NULL REFERENCES plan_pricing(id) ON DELETE CASCADE,
    mp_plan_id VARCHAR(100) UNIQUE NOT NULL,
    mp_plan_status VARCHAR(30) DEFAULT 'active', -- active, inactive
    synced_price DECIMAL(10,2) NOT NULL, -- Precio sincronizado con MP
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_synced_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_subscription_plans_mp_pricing ON subscription_plans_mp(plan_pricing_id);

COMMENT ON TABLE subscription_plans_mp IS 'Cache de planes creados en Mercado Pago';
COMMENT ON COLUMN subscription_plans_mp.synced_price IS 'Ultimo precio sincronizado con MP';

-- =============================================================================
-- SUBSCRIPTIONS (Suscripciones activas por tenant)
-- =============================================================================

CREATE TABLE subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    mp_preapproval_id VARCHAR(100) UNIQUE,
    mp_payer_id VARCHAR(100),
    plan_type VARCHAR(20) NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'pending',
    current_period_start TIMESTAMPTZ,
    current_period_end TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    cancelled_at TIMESTAMPTZ,
    CONSTRAINT valid_subscription_status CHECK (status IN ('pending', 'authorized', 'paused', 'cancelled', 'ended')),
    CONSTRAINT valid_subscription_plan CHECK (plan_type IN ('family', 'premium'))
);

CREATE INDEX idx_subscriptions_tenant ON subscriptions(tenant_id);
CREATE INDEX idx_subscriptions_status ON subscriptions(status) WHERE status = 'authorized';
CREATE INDEX idx_subscriptions_mp_preapproval ON subscriptions(mp_preapproval_id);

COMMENT ON TABLE subscriptions IS 'Suscripciones activas vinculadas a tenants';
COMMENT ON COLUMN subscriptions.status IS 'Estados: pending, authorized, paused, cancelled, ended';

-- Trigger para updated_at
CREATE TRIGGER update_subscriptions_updated_at BEFORE UPDATE ON subscriptions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- SUBSCRIPTION PAYMENTS (Historial de pagos)
-- =============================================================================

CREATE TABLE subscription_payments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subscription_id UUID REFERENCES subscriptions(id) ON DELETE SET NULL,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    mp_payment_id VARCHAR(100) UNIQUE,
    amount DECIMAL(10,2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'ARS',
    status VARCHAR(30) NOT NULL,
    paid_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT positive_amount CHECK (amount > 0),
    CONSTRAINT valid_payment_status CHECK (status IN ('approved', 'pending', 'rejected', 'refunded'))
);

CREATE INDEX idx_subscription_payments_subscription ON subscription_payments(subscription_id);
CREATE INDEX idx_subscription_payments_tenant ON subscription_payments(tenant_id);
CREATE INDEX idx_subscription_payments_status ON subscription_payments(status);

COMMENT ON TABLE subscription_payments IS 'Historial de pagos de suscripciones';

-- =============================================================================
-- COUPONS (Cupones de descuento)
-- =============================================================================

CREATE TABLE coupons (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(50) UNIQUE NOT NULL,
    description VARCHAR(255),
    discount_percent INTEGER NOT NULL,
    applicable_plans VARCHAR(20)[] NOT NULL,
    valid_from TIMESTAMPTZ DEFAULT NOW(),
    valid_until TIMESTAMPTZ,
    max_redemptions INTEGER, -- NULL = ilimitado
    current_redemptions INTEGER DEFAULT 0,
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID REFERENCES users(id),
    CONSTRAINT valid_discount CHECK (discount_percent > 0 AND discount_percent <= 100),
    CONSTRAINT valid_redemptions CHECK (current_redemptions >= 0),
    CONSTRAINT valid_max_redemptions CHECK (max_redemptions IS NULL OR max_redemptions > 0)
);

CREATE INDEX idx_coupons_code ON coupons(code);
CREATE INDEX idx_coupons_active ON coupons(active) WHERE active = true;
CREATE INDEX idx_coupons_valid ON coupons(valid_from, valid_until) WHERE active = true;

COMMENT ON TABLE coupons IS 'Cupones de descuento para suscripciones';
COMMENT ON COLUMN coupons.applicable_plans IS 'Array de planes aplicables: family, premium';

-- =============================================================================
-- COUPON REDEMPTIONS (Historial de uso de cupones)
-- =============================================================================

CREATE TABLE coupon_redemptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    coupon_id UUID NOT NULL REFERENCES coupons(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    subscription_id UUID REFERENCES subscriptions(id) ON DELETE SET NULL,
    discount_applied DECIMAL(10,2) NOT NULL,
    original_price DECIMAL(10,2) NOT NULL,
    final_price DECIMAL(10,2) NOT NULL,
    redeemed_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(coupon_id, tenant_id), -- Un tenant solo puede usar un cupon una vez
    CONSTRAINT positive_discount CHECK (discount_applied >= 0),
    CONSTRAINT positive_original CHECK (original_price >= 0),
    CONSTRAINT positive_final CHECK (final_price >= 0),
    CONSTRAINT valid_final_price CHECK (final_price <= original_price)
);

CREATE INDEX idx_redemptions_coupon ON coupon_redemptions(coupon_id);
CREATE INDEX idx_redemptions_tenant ON coupon_redemptions(tenant_id);

COMMENT ON TABLE coupon_redemptions IS 'Historial de cupones utilizados por tenants';

-- =============================================================================
-- MODIFY TENANTS TABLE (Agregar campos de plan y suscripcion)
-- =============================================================================

ALTER TABLE tenants ADD COLUMN IF NOT EXISTS plan VARCHAR(20) DEFAULT 'starter';
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS subscription_id UUID REFERENCES subscriptions(id) ON DELETE SET NULL;

-- Constraint para plan valido
ALTER TABLE tenants ADD CONSTRAINT valid_tenant_plan CHECK (plan IN ('starter', 'family', 'premium'));

CREATE INDEX IF NOT EXISTS idx_tenants_plan ON tenants(plan);
CREATE INDEX IF NOT EXISTS idx_tenants_subscription ON tenants(subscription_id);

COMMENT ON COLUMN tenants.plan IS 'Plan actual del tenant: starter, family, premium';
COMMENT ON COLUMN tenants.subscription_id IS 'Referencia a la suscripcion activa';

-- =============================================================================
-- FUNCTION: Increment coupon redemptions
-- =============================================================================

CREATE OR REPLACE FUNCTION increment_coupon_redemptions()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE coupons 
    SET current_redemptions = current_redemptions + 1
    WHERE id = NEW.coupon_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_increment_coupon_redemptions
    AFTER INSERT ON coupon_redemptions
    FOR EACH ROW EXECUTE FUNCTION increment_coupon_redemptions();

-- =============================================================================
-- FUNCTION: Validate coupon before redemption
-- =============================================================================

CREATE OR REPLACE FUNCTION validate_coupon_redemption()
RETURNS TRIGGER AS $$
DECLARE
    v_coupon RECORD;
BEGIN
    SELECT * INTO v_coupon FROM coupons WHERE id = NEW.coupon_id;
    
    -- Verificar que el cupon existe y esta activo
    IF NOT FOUND OR NOT v_coupon.active THEN
        RAISE EXCEPTION 'Coupon not found or inactive';
    END IF;
    
    -- Verificar fechas de validez
    IF v_coupon.valid_from > NOW() OR (v_coupon.valid_until IS NOT NULL AND v_coupon.valid_until < NOW()) THEN
        RAISE EXCEPTION 'Coupon is not valid at this time';
    END IF;
    
    -- Verificar limite de usos
    IF v_coupon.max_redemptions IS NOT NULL AND v_coupon.current_redemptions >= v_coupon.max_redemptions THEN
        RAISE EXCEPTION 'Coupon has reached maximum redemptions';
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_validate_coupon_redemption
    BEFORE INSERT ON coupon_redemptions
    FOR EACH ROW EXECUTE FUNCTION validate_coupon_redemption();
