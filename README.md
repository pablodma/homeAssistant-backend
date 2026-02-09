# HomeAI API

Backend API para HomeAI Assistant, construido con FastAPI.

## Proyecto HomeAI

Sistema de asistente virtual del hogar multi-tenant que gestiona presupuestos, agenda, recordatorios y listas de compras via WhatsApp.

### Repositorios relacionados
| Local | GitHub | Deploy |
|-------|--------|--------|
| homeai-api | [homeAssistant-backend](https://github.com/pablodma/homeAssistant-backend) ← ESTE | Railway |
| homeai-web | [homeAssistant-frontend](https://github.com/pablodma/homeAssistant-frontend) | Vercel |
| homeai-assis (futuro) | [homeAssistant-asistant](https://github.com/pablodma/homeAssistant-asistant) | Railway |

## Stack

- **Framework**: FastAPI (Python 3.11+)
- **Database**: PostgreSQL (asyncpg)
- **Auth**: JWT + Google OAuth
- **Deployment**: Railway

## Estructura

```
homeai-api/
├── src/app/
│   ├── config/        # Settings, database
│   ├── routers/       # API endpoints
│   ├── services/      # Business logic
│   ├── repositories/  # Data access
│   ├── schemas/       # Pydantic models
│   └── middleware/    # Auth, CORS
├── tests/
├── docs/
│   └── architecture/
│       ├── decisions/     # ADRs
│       └── threat-model.md
├── scripts/db/
│   └── init.sql       # Schema inicial
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

```bash
# Ejecutar schema inicial
psql $DATABASE_URL -f scripts/db/init.sql
```

## Endpoints

- `GET /` - Root
- `GET /health` - Health check
- `GET /docs` - Swagger UI
- `GET /redoc` - ReDoc
- `POST /api/v1/auth/google/callback` - Google OAuth
- `GET /api/v1/tenants/{tenant_id}` - Tenant info
- ... (ver `/docs` para API completa)

## Deploy en Railway

1. Crear nuevo servicio en Railway
2. Conectar repositorio GitHub
3. Agregar variables de entorno desde `.env.example`
4. Conectar a PostgreSQL existente

## Variables de Entorno

| Variable | Descripción | Requerido |
|----------|-------------|-----------|
| `DATABASE_URL` | PostgreSQL connection string | ✅ |
| `JWT_SECRET_KEY` | Secret para JWT tokens | ✅ |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID | ✅ |
| `GOOGLE_CLIENT_SECRET` | Google OAuth secret | ✅ |
| `CORS_ORIGINS` | URLs permitidas para CORS | ✅ |
| `GITHUB_TOKEN` | Personal Access Token para editar prompts | ❌* |
| `GITHUB_REPO` | Repositorio de prompts (default: pablodma/homeAssistant-asistant) | ❌ |
| `GITHUB_BRANCH` | Branch de prompts (default: master) | ❌ |
| `APP_ENV` | development/production | ❌ |

*`GITHUB_TOKEN` es requerido si querés editar prompts desde el admin panel.

### Configurar GitHub Token

Para habilitar la edición de prompts desde el admin panel:

1. Ir a [GitHub Settings > Developer settings > Personal access tokens > Fine-grained tokens](https://github.com/settings/tokens?type=beta)
2. Crear nuevo token con:
   - **Repository access**: Only select repositories → `homeAssistant-asistant`
   - **Permissions**: Contents → Read and write
3. Copiar el token y agregarlo como variable `GITHUB_TOKEN` en Railway

## Multi-tenancy

- Estrategia: Shared tables con `tenant_id`
- TODA query incluye `WHERE tenant_id = $tenant_id`
- Row Level Security como segunda capa

## Documentación

- [Multi-tenancy Strategy](docs/architecture/decisions/001-multi-tenancy-strategy.md)
- [Threat Model](docs/architecture/threat-model.md)

## Licencia

Privado - Todos los derechos reservados.
