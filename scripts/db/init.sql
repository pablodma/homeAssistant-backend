-- HomeAI Assistant - Schema Inicial PostgreSQL
-- Version: 1.0.0
-- Fecha: 2026-02-07
-- Estrategia Multi-tenancy: Shared tables con tenant_id

-- =============================================================================
-- EXTENSIONES
-- =============================================================================
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- =============================================================================
-- TENANCY (Core)
-- =============================================================================

CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(200) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    active BOOLEAN DEFAULT true,
    settings JSONB DEFAULT '{}'::jsonb,
    CONSTRAINT tenant_name_not_empty CHECK (name <> '')
);

COMMENT ON TABLE tenants IS 'Organizaciones/cuentas que usan el sistema';
COMMENT ON COLUMN tenants.settings IS 'Configuracion JSON: timezone, categorias default, etc';

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    phone VARCHAR(20) NOT NULL,
    email VARCHAR(255),
    display_name VARCHAR(200),
    role VARCHAR(50) DEFAULT 'member',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(phone)
);

CREATE INDEX idx_users_tenant ON users(tenant_id);
CREATE INDEX idx_users_phone ON users(phone);

COMMENT ON TABLE users IS 'Usuarios vinculados a un tenant via telefono';
COMMENT ON COLUMN users.role IS 'Roles: owner, admin, member';

CREATE TABLE invitations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    code VARCHAR(20) NOT NULL UNIQUE,
    created_by UUID REFERENCES users(id),
    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ,
    used_by UUID REFERENCES users(id)
);

CREATE INDEX idx_invitations_code ON invitations(code);
CREATE INDEX idx_invitations_tenant ON invitations(tenant_id);

COMMENT ON TABLE invitations IS 'Codigos de invitacion para vincular telefonos a tenants';

-- =============================================================================
-- FINANCE (Gastos y Presupuestos)
-- =============================================================================

CREATE TABLE budget_categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    monthly_limit DECIMAL(15,2),
    alert_threshold_percent INTEGER DEFAULT 80,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, name)
);

CREATE INDEX idx_budget_cat_tenant ON budget_categories(tenant_id);

COMMENT ON TABLE budget_categories IS 'Categorias de presupuesto por tenant';
COMMENT ON COLUMN budget_categories.alert_threshold_percent IS 'Porcentaje para disparar alerta (default 80%)';

CREATE TABLE expenses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    category_id UUID REFERENCES budget_categories(id) ON DELETE SET NULL,
    amount DECIMAL(15,2) NOT NULL CHECK (amount > 0),
    currency VARCHAR(3) DEFAULT 'ARS',
    description TEXT,
    expense_date DATE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID REFERENCES users(id),
    idempotency_key VARCHAR(100),
    UNIQUE(tenant_id, idempotency_key)
);

CREATE INDEX idx_expenses_tenant_date ON expenses(tenant_id, expense_date);
CREATE INDEX idx_expenses_tenant_category ON expenses(tenant_id, category_id);

COMMENT ON TABLE expenses IS 'Gastos registrados por tenant';
COMMENT ON COLUMN expenses.idempotency_key IS 'Clave para evitar duplicados en operaciones';

-- =============================================================================
-- CALENDAR (Eventos)
-- =============================================================================

CREATE TABLE events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    location VARCHAR(500),
    start_datetime TIMESTAMPTZ NOT NULL,
    end_datetime TIMESTAMPTZ,
    timezone VARCHAR(50) DEFAULT 'America/Argentina/Buenos_Aires',
    recurrence_rule TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID REFERENCES users(id),
    idempotency_key VARCHAR(100),
    UNIQUE(tenant_id, idempotency_key)
);

CREATE INDEX idx_events_tenant_start ON events(tenant_id, start_datetime);
CREATE INDEX idx_events_duplicate_check ON events(tenant_id, start_datetime, title);

COMMENT ON TABLE events IS 'Eventos del calendario por tenant';
COMMENT ON COLUMN events.recurrence_rule IS 'Regla RRULE para eventos recurrentes';

-- =============================================================================
-- REMINDERS (Recordatorios)
-- =============================================================================

CREATE TABLE reminders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    message TEXT NOT NULL,
    trigger_at TIMESTAMPTZ NOT NULL,
    timezone VARCHAR(50) DEFAULT 'America/Argentina/Buenos_Aires',
    recurrence_rule TEXT,
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'sent', 'failed', 'cancelled')),
    last_triggered_at TIMESTAMPTZ,
    next_trigger_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    idempotency_key VARCHAR(100),
    UNIQUE(tenant_id, idempotency_key)
);

CREATE INDEX idx_reminders_pending ON reminders(trigger_at) WHERE status = 'pending';
CREATE INDEX idx_reminders_tenant ON reminders(tenant_id);
CREATE INDEX idx_reminders_user ON reminders(user_id);

COMMENT ON TABLE reminders IS 'Recordatorios programados por usuario';
COMMENT ON COLUMN reminders.status IS 'Estados: pending, processing, sent, failed, cancelled';

-- =============================================================================
-- SHOPPING (Listas de Compras)
-- =============================================================================

CREATE TABLE shopping_lists (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    category VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID REFERENCES users(id),
    UNIQUE(tenant_id, name)
);

CREATE INDEX idx_lists_tenant ON shopping_lists(tenant_id);

COMMENT ON TABLE shopping_lists IS 'Listas de compras por tenant (super, farmacia, etc)';

CREATE TABLE shopping_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    list_id UUID NOT NULL REFERENCES shopping_lists(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(200) NOT NULL,
    quantity DECIMAL(10,2) DEFAULT 1 CHECK (quantity > 0),
    unit VARCHAR(50),
    notes TEXT,
    purchased BOOLEAN DEFAULT false,
    purchased_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    idempotency_key VARCHAR(100)
);

CREATE INDEX idx_items_list ON shopping_items(list_id);
CREATE INDEX idx_items_tenant ON shopping_items(tenant_id);
CREATE INDEX idx_items_not_purchased ON shopping_items(list_id) WHERE purchased = false;

COMMENT ON TABLE shopping_items IS 'Items dentro de listas de compras';

-- =============================================================================
-- CONVERSATIONS (Memoria de Conversaciones)
-- =============================================================================

CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    last_message_at TIMESTAMPTZ DEFAULT NOW(),
    message_count INTEGER DEFAULT 0,
    context JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX idx_conv_tenant_user ON conversations(tenant_id, user_id);
CREATE INDEX idx_conv_last_message ON conversations(last_message_at);

COMMENT ON TABLE conversations IS 'Sesiones de conversacion para contexto del LLM';

CREATE TABLE conversation_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant', 'system', 'tool')),
    content TEXT NOT NULL,
    tool_calls JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_msgs_conv ON conversation_messages(conversation_id, created_at);
CREATE INDEX idx_msgs_tenant ON conversation_messages(tenant_id);

COMMENT ON TABLE conversation_messages IS 'Mensajes individuales de conversaciones';
COMMENT ON COLUMN conversation_messages.tool_calls IS 'Llamadas a tools del LLM en formato JSON';

-- =============================================================================
-- AUDIT (Logs de Auditoria)
-- =============================================================================

CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    correlation_id UUID NOT NULL,
    user_id UUID REFERENCES users(id),
    action VARCHAR(100) NOT NULL,
    entity_type VARCHAR(50),
    entity_id UUID,
    input_data JSONB,
    output_data JSONB,
    status VARCHAR(20) CHECK (status IN ('success', 'error', 'pending')),
    error_message TEXT,
    duration_ms INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_audit_tenant_time ON audit_logs(tenant_id, created_at);
CREATE INDEX idx_audit_correlation ON audit_logs(correlation_id);
CREATE INDEX idx_audit_action ON audit_logs(action);
CREATE INDEX idx_audit_entity ON audit_logs(entity_type, entity_id);

COMMENT ON TABLE audit_logs IS 'Log de todas las acciones para auditoria y debugging';
COMMENT ON COLUMN audit_logs.correlation_id IS 'ID para trazar una solicitud completa';

-- =============================================================================
-- ERROR HANDLING (Cola de Fallos)
-- =============================================================================

CREATE TABLE failed_operations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE SET NULL,
    correlation_id UUID,
    operation_type VARCHAR(100) NOT NULL,
    payload JSONB NOT NULL,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 5,
    next_retry_at TIMESTAMPTZ,
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'dead')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_failed_retry ON failed_operations(next_retry_at) WHERE status = 'pending';
CREATE INDEX idx_failed_status ON failed_operations(status);

COMMENT ON TABLE failed_operations IS 'Dead Letter Queue para operaciones fallidas';
COMMENT ON COLUMN failed_operations.status IS 'Estados: pending (reintentar), processing, completed, dead (abandonado)';

-- =============================================================================
-- ROW LEVEL SECURITY (Opcional - Capa adicional de seguridad)
-- =============================================================================

-- Descomentar para habilitar RLS (requiere configurar app.current_tenant en cada conexion)
/*
ALTER TABLE expenses ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_expenses ON expenses
    USING (tenant_id = current_setting('app.current_tenant')::uuid);

ALTER TABLE events ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_events ON events
    USING (tenant_id = current_setting('app.current_tenant')::uuid);

ALTER TABLE reminders ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_reminders ON reminders
    USING (tenant_id = current_setting('app.current_tenant')::uuid);

ALTER TABLE shopping_lists ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_lists ON shopping_lists
    USING (tenant_id = current_setting('app.current_tenant')::uuid);

ALTER TABLE shopping_items ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_items ON shopping_items
    USING (tenant_id = current_setting('app.current_tenant')::uuid);

ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_conversations ON conversations
    USING (tenant_id = current_setting('app.current_tenant')::uuid);

ALTER TABLE conversation_messages ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_messages ON conversation_messages
    USING (tenant_id = current_setting('app.current_tenant')::uuid);

ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_audit ON audit_logs
    USING (tenant_id = current_setting('app.current_tenant')::uuid);
*/

-- =============================================================================
-- FUNCIONES UTILITARIAS
-- =============================================================================

-- Funcion para actualizar updated_at automaticamente
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers para updated_at
CREATE TRIGGER update_tenants_updated_at BEFORE UPDATE ON tenants
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_events_updated_at BEFORE UPDATE ON events
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_shopping_lists_updated_at BEFORE UPDATE ON shopping_lists
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_failed_operations_updated_at BEFORE UPDATE ON failed_operations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- DATOS INICIALES (Opcional - para testing)
-- =============================================================================

-- Descomentar para insertar datos de prueba
/*
INSERT INTO tenants (id, name, settings) VALUES 
    ('00000000-0000-0000-0000-000000000001', 'Tenant Demo', '{"timezone": "America/Argentina/Buenos_Aires"}'::jsonb);

INSERT INTO users (tenant_id, phone, display_name, role) VALUES 
    ('00000000-0000-0000-0000-000000000001', '+5491123456789', 'Usuario Demo', 'owner');

INSERT INTO budget_categories (tenant_id, name, monthly_limit) VALUES 
    ('00000000-0000-0000-0000-000000000001', 'Supermercado', 100000),
    ('00000000-0000-0000-0000-000000000001', 'Transporte', 30000),
    ('00000000-0000-0000-0000-000000000001', 'Entretenimiento', 50000);
*/
