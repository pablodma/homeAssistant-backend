# HomeAI API

Backend API para HomeAI Assistant, construido con FastAPI.

## Proyecto HomeAI

Sistema de asistente virtual del hogar multi-tenant que gestiona presupuestos, agenda, recordatorios y listas de compras via WhatsApp.

### Repositorios relacionados
| Local | GitHub | Deploy |
|-------|--------|--------|
| homeai-api | [homeAssistant-backend](https://github.com/pablodma/homeAssistant-backend) ← ESTE | Railway |
| homeai-web | [homeAssistant-frontend](https://github.com/pablodma/homeAssistant-frontend) | Vercel |
| homeai-admin | [homeAssistant-admin](https://github.com/pablodma/homeAssistant-admin) | Vercel |
| homeai-assis | [homeAssistant-asistant](https://github.com/pablodma/homeAssistant-asistant) | Railway |

## Stack

- **Framework**: FastAPI (Python 3.11+)
- **Database**: PostgreSQL (asyncpg)
- **Auth**: JWT + Google OAuth (NextAuth en frontend)
- **Payments**: Mercado Pago SDK v2 (suscripciones)
- **Deployment**: Railway

## Estructura

```
homeai-api/
├── src/app/
│   ├── config/          # Settings, database, mercadopago
│   ├── routers/         # API endpoints
│   │   ├── admin.py         # Admin general (agentes, interacciones, stats, QA)
│   │   ├── auth.py          # Google OAuth + JWT
│   │   ├── calendar.py      # Google Calendar integration
│   │   ├── coupons.py       # Cupones (público + admin)
│   │   ├── finance.py       # Gastos, presupuestos
│   │   ├── health.py        # Health check
│   │   ├── onboarding.py    # Configuración inicial del hogar
│   │   ├── plans.py         # Planes y pricing (público + admin)
│   │   ├── subscriptions.py # Suscripciones + webhooks MP
│   │   └── tenants.py       # Gestión de tenants
│   ├── services/        # Business logic
│   │   ├── admin.py         # Agentes, interacciones, QA
│   │   ├── auth.py          # Autenticación
│   │   ├── calendar.py      # Eventos de calendario
│   │   ├── coupon.py        # Validación y gestión de cupones
│   │   ├── finance.py       # Lógica de finanzas
│   │   ├── github.py        # Edición de prompts en GitHub
│   │   ├── google_calendar.py # OAuth y sync con Google Calendar
│   │   ├── qa_reviewer.py   # Revisión de calidad de agentes
│   │   └── subscription.py  # Suscripciones + Mercado Pago
│   ├── repositories/    # Data access (asyncpg)
│   ├── schemas/         # Pydantic models
│   └── middleware/       # Auth (JWT), Correlation ID
├── scripts/db/          # Migraciones SQL
├── docs/
│   ├── TECHNICAL_DEBT.md
│   ├── SERVICES_CONFIGURATION.md
│   ├── prompts/             # Prompts de agentes
│   └── architecture/
│       ├── decisions/       # ADRs
│       └── threat-model.md
├── Dockerfile
└── pyproject.toml
```

## Desarrollo Local

### Requisitos
- Python 3.11+
- PostgreSQL (o usar Railway)

### Setup

```bash
# Crear virtual environment
python -m venv .venv
.venv\Scripts\activate     # Windows
source .venv/bin/activate  # Linux/Mac

# Instalar dependencias
pip install -e ".[dev]"

# Copiar configuración
cp .env.example .env
# Editar .env con tus valores

# Ejecutar
uvicorn src.app.main:app --reload
```

### Base de Datos

Las migraciones están en `scripts/db/` y deben ejecutarse en orden:

| Script | Descripción |
|--------|-------------|
| `init.sql` | Schema inicial: tenants, users, events, reminders, shopping lists |
| `002_calendar_google_integration.sql` | Google Calendar OAuth y sync |
| `003_agent_admin.sql` | Prompts de agentes e interacciones |
| `004_increase_phone_length.sql` | Ampliar campo phone a VARCHAR(100) |
| `005_multitenancy.sql` | Multi-tenancy dinámico, phone_tenant_mapping |
| `005_1_migrate_current_user.sql` | Migrar datos de usuario existente |
| `006_quality_issues.sql` | Issues de calidad (QA) |
| `007_subscriptions_coupons_pricing.sql` | Suscripciones, cupones, pricing de planes |
| `007_qa_reviews.sql` | Ciclos de revisión QA y revisiones de prompts |
| `008_plan_services.sql` | Servicios habilitados por plan |

```bash
# Ejecutar migración
psql $DATABASE_URL -f scripts/db/init.sql
```

## Endpoints

### Públicos
- `GET /health` - Health check
- `GET /docs` - Swagger UI
- `GET /redoc` - ReDoc
- `POST /api/v1/auth/google/callback` - Google OAuth callback
- `POST /api/v1/auth/google/token` - Exchange ID token por JWT
- `GET /api/v1/plans` - Lista de planes con pricing
- `GET /api/v1/plans/{plan_type}` - Detalle de un plan
- `GET /api/v1/plans/compare/{from}/{to}` - Comparar planes
- `GET /api/v1/coupons/generate-code` - Generar código de cupón

### Protegidos (requieren JWT)
- `POST /api/v1/onboarding` - Completar onboarding del hogar
- `GET /api/v1/tenants/{tenant_id}` - Info del tenant
- `POST /api/v1/subscriptions` - Crear suscripción (redirect a MP)
- `GET /api/v1/subscriptions/me` - Estado de suscripción actual
- `POST /api/v1/subscriptions/cancel` - Cancelar suscripción
- `POST /api/v1/subscriptions/pause` - Pausar suscripción
- `GET /api/v1/subscriptions/payments` - Historial de pagos
- `POST /api/v1/subscriptions/sync` - Sincronizar con MP
- `GET /api/v1/calendar/events` - Eventos del calendario
- `POST /api/v1/calendar/oauth/start` - Iniciar OAuth con Google Calendar
- `GET /api/v1/finance/expenses` - Listar gastos
- `POST /api/v1/finance/expenses` - Crear gasto

### Admin
- `GET /api/v1/tenants/{id}/admin/agents` - Lista de agentes
- `GET/PUT /api/v1/tenants/{id}/admin/agents/{name}/prompt` - Gestión de prompts
- `GET /api/v1/tenants/{id}/admin/interactions` - Interacciones
- `GET /api/v1/tenants/{id}/admin/stats` - Estadísticas
- `GET /api/v1/tenants/{id}/admin/quality-issues` - Issues de calidad
- `GET /api/v1/admin/plans` - Lista planes (admin)
- `PUT /api/v1/admin/plans/{plan_type}` - Actualizar plan
- `GET /api/v1/admin/services` - Catálogo de servicios
- `GET /api/v1/admin/coupons` - Lista de cupones
- `POST /api/v1/admin/coupons` - Crear cupón
- `PATCH /api/v1/admin/coupons/{id}` - Actualizar cupón
- `DELETE /api/v1/admin/coupons/{id}` - Eliminar cupón

### Webhooks
- `POST /api/v1/webhooks/mercadopago` - Webhook de Mercado Pago

Ver `/docs` para la API completa con schemas.

## Deploy en Railway

1. Crear nuevo servicio en Railway
2. Conectar repositorio GitHub
3. Agregar variables de entorno desde `.env.example`
4. Conectar a PostgreSQL existente

## Variables de Entorno

### Aplicación
| Variable | Descripción | Requerido |
|----------|-------------|-----------|
| `DATABASE_URL` | PostgreSQL connection string | Si |
| `APP_ENV` | `development` / `production` | No |
| `JWT_SECRET_KEY` | Secret para JWT tokens | Si |
| `CORS_ORIGINS` | URLs permitidas para CORS (comma-separated) | Si |
| `FRONTEND_URL` | URL del frontend (para redirects de MP) | Si |

### Google OAuth
| Variable | Descripción | Requerido |
|----------|-------------|-----------|
| `GOOGLE_CLIENT_ID` | Google OAuth client ID | Si |
| `GOOGLE_CLIENT_SECRET` | Google OAuth secret | Si |

### Google Calendar
| Variable | Descripción | Requerido |
|----------|-------------|-----------|
| `CALENDAR_OAUTH_SUCCESS_URL` | URL redirect después de conectar calendario | No |
| `CALENDAR_OAUTH_ERROR_URL` | URL redirect si falla conexión de calendario | No |

### Mercado Pago
| Variable | Descripción | Requerido |
|----------|-------------|-----------|
| `MP_ACCESS_TOKEN` | Access token de Mercado Pago | Si* |
| `MP_PUBLIC_KEY` | Public key de Mercado Pago | Si* |
| `MP_WEBHOOK_SECRET` | Secret para validar webhooks de MP | No |
| `MP_SANDBOX` | `true` / `false` (modo sandbox) | No |

*Requerido para el flujo de suscripciones y pagos.

### GitHub (prompts)
| Variable | Descripción | Requerido |
|----------|-------------|-----------|
| `GITHUB_TOKEN` | Personal Access Token para editar prompts | No* |
| `GITHUB_REPO` | Repositorio de prompts (default: `pablodma/homeAssistant-asistant`) | No |
| `GITHUB_BRANCH` | Branch de prompts (default: `master`) | No |

*Requerido si querés editar prompts desde el admin panel.

### OpenAI
| Variable | Descripción | Requerido |
|----------|-------------|-----------|
| `OPENAI_API_KEY` | API key de OpenAI | No* |

*Usado para event detection en el calendario.

## Multi-tenancy

- Estrategia: Shared tables con `tenant_id`
- TODA query incluye `WHERE tenant_id = $tenant_id`
- Row Level Security como segunda capa
- Ver [ADR-001](docs/architecture/decisions/001-multi-tenancy-strategy.md)

## Documentación

- [Multi-tenancy Strategy](docs/architecture/decisions/001-multi-tenancy-strategy.md)
- [Threat Model](docs/architecture/threat-model.md)
- [Technical Debt & Roadmap](docs/TECHNICAL_DEBT.md)
- [Configuración de Servicios](docs/SERVICES_CONFIGURATION.md)

## Licencia

Privado - Todos los derechos reservados.
