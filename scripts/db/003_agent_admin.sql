-- Migration: Agent Admin Tables
-- Description: Tables for agent prompts, interactions, and bot-related data
-- Date: 2026-02-08

-- =====================================================
-- AGENT PROMPTS TABLE
-- Stores editable prompts for each agent
-- =====================================================

CREATE TABLE IF NOT EXISTS agent_prompts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    agent_name VARCHAR(50) NOT NULL,
    prompt_content TEXT NOT NULL,
    version INTEGER DEFAULT 1,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by VARCHAR(100)
);

-- Partial unique index for active prompts
CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_active_prompt 
ON agent_prompts(tenant_id, agent_name) WHERE is_active = true;

CREATE INDEX IF NOT EXISTS idx_agent_prompts_tenant ON agent_prompts(tenant_id);
CREATE INDEX IF NOT EXISTS idx_agent_prompts_agent ON agent_prompts(tenant_id, agent_name);

COMMENT ON TABLE agent_prompts IS 'Editable prompts for each agent, versioned';
COMMENT ON COLUMN agent_prompts.agent_name IS 'Agent identifier: router, finance, calendar, reminder, shopping, vehicle';
COMMENT ON COLUMN agent_prompts.version IS 'Version number for tracking changes';
COMMENT ON COLUMN agent_prompts.is_active IS 'Only one active prompt per agent per tenant';

-- =====================================================
-- AGENT INTERACTIONS TABLE
-- Logs all bot interactions for analytics
-- =====================================================

CREATE TABLE IF NOT EXISTS agent_interactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_phone VARCHAR(20) NOT NULL,
    user_name VARCHAR(100),
    message_in TEXT NOT NULL,
    message_out TEXT NOT NULL,
    agent_used VARCHAR(50) NOT NULL,
    sub_agent_used VARCHAR(50),
    tokens_in INTEGER,
    tokens_out INTEGER,
    response_time_ms INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB
);

CREATE INDEX IF NOT EXISTS idx_interactions_tenant_date ON agent_interactions(tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_interactions_user ON agent_interactions(tenant_id, user_phone);
CREATE INDEX IF NOT EXISTS idx_interactions_agent ON agent_interactions(tenant_id, agent_used);

COMMENT ON TABLE agent_interactions IS 'Log of all bot interactions for analytics and debugging';
COMMENT ON COLUMN agent_interactions.agent_used IS 'Main agent that processed the message';
COMMENT ON COLUMN agent_interactions.sub_agent_used IS 'Sub-agent if delegation occurred';
COMMENT ON COLUMN agent_interactions.tokens_in IS 'Input tokens consumed by LLM';
COMMENT ON COLUMN agent_interactions.tokens_out IS 'Output tokens consumed by LLM';

-- =====================================================
-- CHAT SESSIONS TABLE
-- Tracks conversation sessions
-- =====================================================

CREATE TABLE IF NOT EXISTS chat_sessions (
    session_key VARCHAR(100) PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    phone VARCHAR(20) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_sessions_tenant ON chat_sessions(tenant_id);

COMMENT ON TABLE chat_sessions IS 'Tracks conversation sessions for memory management';

-- =====================================================
-- CHAT MESSAGES TABLE
-- Stores conversation history
-- =====================================================

CREATE TABLE IF NOT EXISTS chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_key VARCHAR(100) NOT NULL REFERENCES chat_sessions(session_key) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON chat_messages(session_key, created_at DESC);

COMMENT ON TABLE chat_messages IS 'Conversation history for context';

-- =====================================================
-- REMINDERS TABLE
-- Stores user reminders
-- =====================================================

CREATE TABLE IF NOT EXISTS reminders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_phone VARCHAR(20) NOT NULL,
    message TEXT NOT NULL,
    trigger_date DATE,
    trigger_time VARCHAR(5),
    recurrence VARCHAR(20) DEFAULT 'none',
    is_completed BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_reminders_tenant ON reminders(tenant_id, user_phone);
CREATE INDEX IF NOT EXISTS idx_reminders_date ON reminders(trigger_date) WHERE is_completed = false;

COMMENT ON TABLE reminders IS 'User reminders and alerts';

-- =====================================================
-- SHOPPING ITEMS TABLE
-- Stores shopping list items
-- =====================================================

CREATE TABLE IF NOT EXISTS shopping_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_phone VARCHAR(20) NOT NULL,
    list_name VARCHAR(100) DEFAULT 'Supermercado',
    item_name VARCHAR(200) NOT NULL,
    quantity DECIMAL(10,2) DEFAULT 1,
    unit VARCHAR(20),
    is_purchased BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_shopping_tenant ON shopping_items(tenant_id, list_name);
CREATE INDEX IF NOT EXISTS idx_shopping_user ON shopping_items(tenant_id, user_phone);

COMMENT ON TABLE shopping_items IS 'Shopping list items';

-- =====================================================
-- VEHICLES TABLE
-- Stores vehicle information
-- =====================================================

CREATE TABLE IF NOT EXISTS vehicles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_phone VARCHAR(20) NOT NULL,
    vehicle_name VARCHAR(100),
    brand VARCHAR(50) NOT NULL,
    model VARCHAR(50) NOT NULL,
    year INTEGER,
    plate VARCHAR(20),
    mileage INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT unique_vehicle_plate UNIQUE (tenant_id, plate)
);

CREATE INDEX IF NOT EXISTS idx_vehicles_tenant ON vehicles(tenant_id, user_phone);

COMMENT ON TABLE vehicles IS 'User vehicles';

-- =====================================================
-- VEHICLE SERVICES TABLE
-- Stores vehicle maintenance history
-- =====================================================

CREATE TABLE IF NOT EXISTS vehicle_services (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vehicle_id UUID NOT NULL REFERENCES vehicles(id) ON DELETE CASCADE,
    service_type VARCHAR(100) NOT NULL,
    service_date DATE NOT NULL,
    mileage INTEGER,
    cost DECIMAL(12,2),
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_vehicle_services ON vehicle_services(vehicle_id, service_date DESC);

COMMENT ON TABLE vehicle_services IS 'Vehicle service and maintenance history';

-- =====================================================
-- VEHICLE REMINDERS TABLE
-- Stores vehicle-related reminders (VTV, insurance, etc.)
-- =====================================================

CREATE TABLE IF NOT EXISTS vehicle_reminders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vehicle_id UUID NOT NULL REFERENCES vehicles(id) ON DELETE CASCADE,
    reminder_type VARCHAR(50) NOT NULL,
    due_date DATE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT unique_vehicle_reminder UNIQUE (vehicle_id, reminder_type)
);

CREATE INDEX IF NOT EXISTS idx_vehicle_reminders ON vehicle_reminders(vehicle_id, due_date);

COMMENT ON TABLE vehicle_reminders IS 'Vehicle-related reminders (VTV, insurance, plates)';

-- =====================================================
-- INSERT DEFAULT PROMPTS
-- =====================================================

INSERT INTO agent_prompts (tenant_id, agent_name, prompt_content, version)
SELECT 
    '00000000-0000-0000-0000-000000000001'::UUID,
    'router',
    'Agente Orquestador Principal HomeAI. Te llamas Casita.

## Identidad

Eres el asistente virtual del hogar HomeAI. Ayudás a los usuarios a gestionar su hogar de forma simple y conversacional.

## Tus Capacidades

Tenés acceso a estas herramientas especializadas:

1. **finance_agent** - Para todo lo relacionado con dinero: registrar gastos, consultar cuánto se gastó, ver presupuestos.

2. **calendar_agent** - Para gestionar eventos y agenda: crear citas, ver qué hay programado, cancelar eventos.

3. **reminder_agent** - Para recordatorios y alertas: crear recordatorios, ver pendientes, cancelar recordatorios.

4. **shopping_agent** - Para listas de compras: agregar items, ver listas, marcar como comprado.

5. **vehicle_agent** - Para gestión del vehículo: registrar services, ver vencimientos (VTV, seguro), consultas de mantenimiento.

## Cómo Actuar

1. **Analizá el mensaje del usuario**
2. **Si está claro qué quiere** → Usá la herramienta correspondiente
3. **Si NO está claro** → Respondé directamente pidiendo clarificación (SIN usar herramientas)

## Tono y Estilo

- Español argentino informal (vos, gastaste, tenés)
- Respuestas concisas y directas
- Amigable pero no excesivamente efusivo
- Si algo no está claro, preguntá antes de asumir',
    1
WHERE NOT EXISTS (
    SELECT 1 FROM agent_prompts 
    WHERE tenant_id = '00000000-0000-0000-0000-000000000001' AND agent_name = 'router'
);
