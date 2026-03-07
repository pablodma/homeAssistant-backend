# homeai-api — API Agent

Backend FastAPI multi-tenant para HomeAI Assistant. Gestiona auth, finanzas, calendario, onboarding, suscripciones y endpoints para el bot.

## Ownership

Este agente es responsable de TODO lo que vive en `homeai-api/`. No modifica otros servicios.

## Stack

- Python 3.11, FastAPI, asyncpg, PostgreSQL
- Pydantic v2 + pydantic-settings
- Payments: Lemon Squeezy (via httpx)
- Auth: Google OAuth → JWT
- Package manager: `uv` (`uv sync`, `uv run pytest`)

## Estructura

```
src/app/
├── main.py               # FastAPI app, lifespan, CORS, routers
├── config/
│   ├── settings.py       # Pydantic BaseSettings (lru_cache)
│   └── database.py       # asyncpg pool
├── routers/              # HTTP endpoints (thin layer)
├── services/             # Business logic
├── repositories/         # Data access (asyncpg queries)
├── schemas/              # Pydantic models
└── middleware/           # CorrelationId, JWT auth
scripts/db/               # Migraciones SQL (NNN_nombre.sql)
tests/
```

## Layer Rules

`router` → `service` → `repository` → DB. Nunca saltear capas.
- Routers: solo validación HTTP, auth check, llamar service
- Services: lógica de negocio, orquestar repositories
- Repositories: queries asyncpg, retornar `None` para not-found
- Services traducen `None` → excepción de dominio

## Comandos

```bash
# Setup
uv sync --all-groups

# Dev server
uv run uvicorn src.app.main:app --reload --port 8000

# Tests
uv run pytest tests/ -v

# Linting
uv run ruff check src/ && uv run black --check src/

# Run single migration
uv run python scripts/run_migration.py scripts/db/NNN_nombre.sql
```

## Migraciones SQL

- Archivos en `scripts/db/` con prefijo numérico único (`NNN_nombre.sql`)
- Última migración: `022_add_conversation_summary.sql`
- Próxima: `023_...`
- **Nunca reusar número** — ya hay conflicto en `014` (dos archivos)
- Correr con `python scripts/run_migration.py` contra la DB correcta

## Multi-Tenancy

- Todo endpoint de datos incluye `tenant_id` extraído del JWT
- Todos los queries asyncpg filtran por `tenant_id`
- Tabla `users`: fuente de verdad para phone→tenant (PhoneResolver del bot la consulta)
- Endpoint público sin auth: `GET /api/v1/phone/lookup?phone=...`

## Auth

- Google OAuth → callback → JWT con `user_id`, `tenant_id`, `role`
- Bot usa Bearer token de servicio (no JWT de usuario)
- `validate_production_secrets()` en startup — bloquea si JWT_SECRET_KEY es default

## Endpoints Clave para el Bot

```
GET  /api/v1/phone/lookup?phone={e164}          → { found, tenant_id, user_name, ... }
POST /api/v1/tenants/{id}/agent/expense          → registrar gasto
GET  /api/v1/tenants/{id}/agent/expenses         → listar gastos
POST /api/v1/tenants/{id}/agent/calendar/events  → crear evento
GET  /api/v1/agent-onboarding/status             → estado onboarding por agente
POST /api/v1/agent-onboarding/complete           → marcar onboarding completo
POST /api/v1/onboarding/web-link                 → generar link onboarding para unregistered
```

## Variables de Entorno Requeridas

`DATABASE_URL`, `JWT_SECRET_KEY`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `OPENAI_API_KEY`, `LS_API_KEY`, `LS_WEBHOOK_SECRET`, `GITHUB_TOKEN`, `FRONTEND_URL`, `CORS_ORIGINS`

Ver `.env.example` para valores de desarrollo.

## Guardrails

- Nunca exponer `DATABASE_URL` o `JWT_SECRET_KEY` en logs
- `/docs` y `/redoc` están abiertos — no agregar info sensible en schemas
- Migrations en prod: revisar SQL manualmente antes de ejecutar
- No modificar `scripts/db/` existentes — solo agregar nuevos archivos
- Si hay cambio de schema que rompe el bot (tabla `users`, `agent_interactions`) → escalar al Leader
