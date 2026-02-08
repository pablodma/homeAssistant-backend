-- HomeAI Assistant - Calendar Google Integration Migration
-- Version: 1.0.1
-- Fecha: 2026-02-07
-- Descripción: Agrega soporte para integración con Google Calendar

-- =============================================================================
-- GOOGLE CALENDAR CREDENTIALS
-- =============================================================================

CREATE TABLE google_calendar_credentials (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    access_token TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    token_expires_at TIMESTAMPTZ NOT NULL,
    calendar_id VARCHAR(255) DEFAULT 'primary',
    scopes TEXT[] DEFAULT ARRAY['https://www.googleapis.com/auth/calendar.events', 'https://www.googleapis.com/auth/calendar.readonly'],
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_google_creds_user ON google_calendar_credentials(user_id);
CREATE INDEX idx_google_creds_tenant ON google_calendar_credentials(tenant_id);
CREATE INDEX idx_google_creds_expires ON google_calendar_credentials(token_expires_at);

COMMENT ON TABLE google_calendar_credentials IS 'OAuth tokens para acceso a Google Calendar por usuario';
COMMENT ON COLUMN google_calendar_credentials.calendar_id IS 'ID del calendario de Google (default: primary)';
COMMENT ON COLUMN google_calendar_credentials.scopes IS 'Scopes OAuth autorizados';

-- =============================================================================
-- EVENTS TABLE - GOOGLE CALENDAR SYNC COLUMNS
-- =============================================================================

-- Agregar columna para sincronización con Google Calendar
ALTER TABLE events ADD COLUMN IF NOT EXISTS google_event_id VARCHAR(255);
ALTER TABLE events ADD COLUMN IF NOT EXISTS google_calendar_id VARCHAR(255);
ALTER TABLE events ADD COLUMN IF NOT EXISTS sync_status VARCHAR(20) DEFAULT 'local' 
    CHECK (sync_status IN ('local', 'synced', 'pending_sync', 'sync_failed'));
ALTER TABLE events ADD COLUMN IF NOT EXISTS last_synced_at TIMESTAMPTZ;
ALTER TABLE events ADD COLUMN IF NOT EXISTS source VARCHAR(20) DEFAULT 'app' 
    CHECK (source IN ('app', 'google'));

-- Índice único para evitar duplicados de Google
CREATE UNIQUE INDEX IF NOT EXISTS idx_events_google_id 
    ON events(tenant_id, google_event_id) 
    WHERE google_event_id IS NOT NULL;

-- Índice para búsqueda de eventos pendientes de sincronización
CREATE INDEX IF NOT EXISTS idx_events_pending_sync 
    ON events(tenant_id, sync_status) 
    WHERE sync_status = 'pending_sync';

COMMENT ON COLUMN events.google_event_id IS 'ID del evento en Google Calendar para sincronización';
COMMENT ON COLUMN events.google_calendar_id IS 'ID del calendario de Google donde está el evento';
COMMENT ON COLUMN events.sync_status IS 'Estado de sincronización: local, synced, pending_sync, sync_failed';
COMMENT ON COLUMN events.source IS 'Origen del evento: app (creado aquí) o google (importado)';

-- =============================================================================
-- TRIGGER PARA UPDATED_AT
-- =============================================================================

CREATE TRIGGER update_google_creds_updated_at BEFORE UPDATE ON google_calendar_credentials
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- OAUTH STATE TABLE (para flujo OAuth via WhatsApp)
-- =============================================================================

CREATE TABLE oauth_states (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    state VARCHAR(100) NOT NULL UNIQUE,
    user_phone VARCHAR(20) NOT NULL,
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    redirect_url TEXT,
    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_oauth_state ON oauth_states(state);
CREATE INDEX idx_oauth_expires ON oauth_states(expires_at) WHERE used_at IS NULL;

COMMENT ON TABLE oauth_states IS 'Estados temporales para flujo OAuth via WhatsApp';
COMMENT ON COLUMN oauth_states.state IS 'Token único para validar callback OAuth';
COMMENT ON COLUMN oauth_states.user_phone IS 'Teléfono del usuario para asociar credenciales';
