#!/usr/bin/env python3
"""Run calendar migration on Railway PostgreSQL."""

import psycopg2

conn = psycopg2.connect(
    host='nozomi.proxy.rlwy.net',
    port=25188,
    user='postgres',
    password='WhJXHLOPxCZtTlIQgpMLDdMeiqcDEWuu',
    dbname='railway'
)
conn.autocommit = True
cur = conn.cursor()

# Verificar tablas existentes
print("Verificando tablas existentes...")
cur.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public';")
tables = [row[0] for row in cur.fetchall()]
print(f"Tablas: {tables}")

# Verificar si events existe
if 'events' not in tables:
    print("\n[!] La tabla 'events' no existe. Creandola primero...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            title VARCHAR(200) NOT NULL,
            description TEXT,
            location VARCHAR(500),
            start_datetime TIMESTAMPTZ NOT NULL,
            end_datetime TIMESTAMPTZ,
            timezone VARCHAR(50) DEFAULT 'America/Argentina/Buenos_Aires',
            recurrence_rule TEXT,
            created_by UUID REFERENCES users(id) ON DELETE SET NULL,
            idempotency_key VARCHAR(100),
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(tenant_id, idempotency_key)
        );
        
        CREATE INDEX IF NOT EXISTS idx_events_tenant ON events(tenant_id);
        CREATE INDEX IF NOT EXISTS idx_events_start ON events(tenant_id, start_datetime);
        
        CREATE TRIGGER update_events_updated_at BEFORE UPDATE ON events
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    """)
    print("[OK] Tabla events creada")

print("\nEjecutando migracion de Calendar Google Integration...")

# Google Calendar Credentials
print("Creando tabla google_calendar_credentials...")
cur.execute("""
    CREATE TABLE IF NOT EXISTS google_calendar_credentials (
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
""")

cur.execute("CREATE INDEX IF NOT EXISTS idx_google_creds_user ON google_calendar_credentials(user_id);")
cur.execute("CREATE INDEX IF NOT EXISTS idx_google_creds_tenant ON google_calendar_credentials(tenant_id);")
cur.execute("CREATE INDEX IF NOT EXISTS idx_google_creds_expires ON google_calendar_credentials(token_expires_at);")
print("[OK] google_calendar_credentials creada")

# Agregar columnas a events
print("Agregando columnas de sync a events...")
cur.execute("ALTER TABLE events ADD COLUMN IF NOT EXISTS google_event_id VARCHAR(255);")
cur.execute("ALTER TABLE events ADD COLUMN IF NOT EXISTS google_calendar_id VARCHAR(255);")
cur.execute("ALTER TABLE events ADD COLUMN IF NOT EXISTS last_synced_at TIMESTAMPTZ;")

# sync_status con CHECK
cur.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                       WHERE table_name = 'events' AND column_name = 'sync_status') THEN
            ALTER TABLE events ADD COLUMN sync_status VARCHAR(20) DEFAULT 'local';
            ALTER TABLE events ADD CONSTRAINT events_sync_status_check 
                CHECK (sync_status IN ('local', 'synced', 'pending_sync', 'sync_failed'));
        END IF;
    END $$;
""")

# source con CHECK  
cur.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                       WHERE table_name = 'events' AND column_name = 'source') THEN
            ALTER TABLE events ADD COLUMN source VARCHAR(20) DEFAULT 'app';
            ALTER TABLE events ADD CONSTRAINT events_source_check 
                CHECK (source IN ('app', 'google'));
        END IF;
    END $$;
""")
print("[OK] Columnas de sync agregadas")

# Índices
print("Creando índices...")
cur.execute("""
    CREATE UNIQUE INDEX IF NOT EXISTS idx_events_google_id 
    ON events(tenant_id, google_event_id) 
    WHERE google_event_id IS NOT NULL;
""")
cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_events_pending_sync 
    ON events(tenant_id, sync_status) 
    WHERE sync_status = 'pending_sync';
""")
print("[OK] Indices creados")

# Trigger para updated_at en google_calendar_credentials
print("Creando trigger...")
cur.execute("""
    DROP TRIGGER IF EXISTS update_google_creds_updated_at ON google_calendar_credentials;
    CREATE TRIGGER update_google_creds_updated_at BEFORE UPDATE ON google_calendar_credentials
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
""")
print("[OK] Trigger creado")

# OAuth States
print("Creando tabla oauth_states...")
cur.execute("""
    CREATE TABLE IF NOT EXISTS oauth_states (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        state VARCHAR(100) NOT NULL UNIQUE,
        user_phone VARCHAR(20) NOT NULL,
        tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
        redirect_url TEXT,
        expires_at TIMESTAMPTZ NOT NULL,
        used_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ DEFAULT NOW()
    );
""")
cur.execute("CREATE INDEX IF NOT EXISTS idx_oauth_state ON oauth_states(state);")
cur.execute("CREATE INDEX IF NOT EXISTS idx_oauth_expires ON oauth_states(expires_at) WHERE used_at IS NULL;")
print("[OK] oauth_states creada")

conn.close()
print("\nMigracion completada exitosamente!")
