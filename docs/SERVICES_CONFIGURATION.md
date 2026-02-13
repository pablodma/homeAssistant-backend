# HomeAI - Guía de Configuración de Servicios Externos

**Última actualización:** 2026-02-13  
**Propósito:** Documentar la configuración necesaria de todos los servicios externos que utiliza HomeAI

---

## Tabla de Contenidos

1. [Arquitectura General](#arquitectura-general)
2. [Google OAuth](#1-google-oauth)
3. [Meta/WhatsApp Business](#2-metawhatsapp-business)
4. [Railway (Backend)](#3-railway-backend)
5. [Vercel (Frontend)](#4-vercel-frontend)
6. [OpenAI](#5-openai)
7. [Mercado Pago](#6-mercado-pago)
8. [Checklist de Configuración](#checklist-de-configuración)
9. [Troubleshooting](#troubleshooting)

---

## Arquitectura General

```
┌──────────────────────────────────────────────────────────────────────────┐
│                              FRONTEND                                    │
│  ┌──────────────────────────────┐  ┌──────────────────────────────┐     │
│  │   homeai-web (Vercel)        │  │   homeai-admin (Vercel)      │     │
│  │   Next.js 14 + NextAuth      │  │   Next.js 14 + NextAuth      │     │
│  │   Landing, Dashboard, Pago   │  │   Agentes, QA, Pricing, etc. │     │
│  └──────────────────────────────┘  └──────────────────────────────┘     │
└──────────────────────────────────────────────────────────────────────────┘
                        │                           │
                        │ API calls (JWT)           │
                        ▼                           ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                              BACKEND                                     │
│  ┌──────────────────────────┐  ┌──────────────────────────────┐         │
│  │ homeai-api (Railway)     │  │ homeai-assis (Railway)        │         │
│  │ FastAPI + PostgreSQL     │  │ FastAPI + LangChain + OpenAI  │         │
│  │ Auth, Admin, Finance,    │  │ WhatsApp Webhook + Bot Agents │         │
│  │ Subscriptions, Calendar  │  │                               │         │
│  └──────────────────────────┘  └──────────────────────────────┘         │
│              │                              │                            │
│              ▼                              ▼                            │
│  ┌──────────────────────────────────────────────────────────────┐       │
│  │                 PostgreSQL (Railway)                          │       │
│  │         Postgres-Home Asisst (shared database)                │       │
│  └──────────────────────────────────────────────────────────────┘       │
└──────────────────────────────────────────────────────────────────────────┘
                        │
                        │ External APIs
                        ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                     SERVICIOS EXTERNOS                                   │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐        │
│  │  Google    │  │   Meta/    │  │   OpenAI   │  │  Mercado   │        │
│  │  OAuth     │  │  WhatsApp  │  │   (AI)     │  │   Pago     │        │
│  │  (Login)   │  │ (Messaging)│  │            │  │ (Payments) │        │
│  └────────────┘  └────────────┘  └────────────┘  └────────────┘        │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 1. Google OAuth

**Propósito:** Autenticación de usuarios en el panel web y admin

### Configuración en Google Cloud Console

1. **Acceder a Google Cloud Console**
   - URL: https://console.cloud.google.com/

2. **Crear/Seleccionar Proyecto**
   - Proyecto actual: `homeai-assistant` (o similar)

3. **Configurar OAuth Consent Screen**
   - Navigation: APIs & Services → OAuth consent screen
   - User Type: External (para desarrollo)
   - App name: HomeAI Assistant
   - User support email: (tu email)
   - Scopes: `email`, `profile`, `openid`

4. **Crear Credenciales OAuth 2.0**
   - Navigation: APIs & Services → Credentials → Create Credentials → OAuth client ID
   - Application type: Web application
   - Name: HomeAI Web Client
   
   **Authorized JavaScript origins:**
   ```
   http://localhost:3000
   https://home-assistant-frontend-brown.vercel.app
   https://homeai-admin-three.vercel.app
   ```
   
   **Authorized redirect URIs:**
   ```
   http://localhost:3000/api/auth/callback/google
   http://localhost:3001/api/auth/callback/google
   https://home-assistant-frontend-brown.vercel.app/api/auth/callback/google
   https://homeai-admin-three.vercel.app/api/auth/callback/google
   ```

5. **Obtener credenciales**
   - Client ID: `xxxxxxxx.apps.googleusercontent.com`
   - Client Secret: `GOCSPX-xxxxxxxxxx`

### Variables de Entorno

| Variable | Ubicación | Valor |
|----------|-----------|-------|
| `GOOGLE_CLIENT_ID` | Vercel homeai-web (production) | `xxxxxx.apps.googleusercontent.com` |
| `GOOGLE_CLIENT_SECRET` | Vercel homeai-web (production) | `GOCSPX-xxxxxx` |
| `GOOGLE_CLIENT_ID` | Vercel homeai-admin (production) | (mismo) |
| `GOOGLE_CLIENT_SECRET` | Vercel homeai-admin (production) | (mismo) |
| `GOOGLE_CLIENT_ID` | Railway (homeAssistant-backend) | (mismo) |
| `GOOGLE_CLIENT_ID` | Local (.env.local) | (mismo) |
| `GOOGLE_CLIENT_SECRET` | Local (.env.local) | (mismo) |

### Errores Comunes

| Error | Causa | Solución |
|-------|-------|----------|
| `401: deleted_client` | Client ID de app eliminada | Crear nuevas credenciales |
| `redirect_uri_mismatch` | URI no configurada | Agregar URI en Console |
| `access_denied` | Consent screen no publicado | Publicar app o agregar test users |

---

## 2. Meta/WhatsApp Business

**Propósito:** Recepción y envío de mensajes de WhatsApp para el bot

### Configuración en Meta for Developers

1. **Acceder a Meta for Developers**
   - URL: https://developers.facebook.com/

2. **Crear/Seleccionar App**
   - Tipo: Business
   - Nombre: HomeAI Assistant

3. **Agregar Producto WhatsApp**
   - Dashboard → Add Products → WhatsApp → Set up

4. **Configurar API**
   - WhatsApp → API Setup
   - Obtener:
     - **Phone Number ID**: ID del número de prueba/producción
     - **Access Token**: Token temporal (24h) o permanente

5. **Configurar Webhook**
   - WhatsApp → Configuration → Edit
   - Callback URL: `https://homeai-assis-production-xxxx.up.railway.app/api/v1/whatsapp/webhook`
   - Verify Token: (definido en `WHATSAPP_VERIFY_TOKEN`)
   - Webhook Fields: `messages` (suscribirse)

### Variables de Entorno

| Variable | Servicio | Descripción |
|----------|----------|-------------|
| `WHATSAPP_ACCESS_TOKEN` | homeai-assis | Token de acceso (temporal o permanente) |
| `WHATSAPP_PHONE_NUMBER_ID` | homeai-assis | ID del número de WhatsApp |
| `WHATSAPP_VERIFY_TOKEN` | homeai-assis | Token de verificación del webhook |

### Tokens de Acceso

**Token Temporal (desarrollo):**
- Duración: 24 horas
- Obtención: API Setup → Generate temporary access token
- Debe regenerarse cada día

**Token Permanente (producción):**
1. System User → Create System User
2. Asignar assets (WhatsApp Business Account)
3. Generate Token → Seleccionar permisos
4. Permisos necesarios: `whatsapp_business_messaging`, `whatsapp_business_management`

### Errores Comunes

| Error | Causa | Solución |
|-------|-------|----------|
| `OAuthException: Session expired` | Token temporal expirado | Generar nuevo token |
| `#100 Invalid parameter` | Phone Number ID incorrecto | Verificar ID en API Setup |
| Mensajes no llegan | Webhook no verificado | Re-verificar webhook |
| Mensajes salen pero no entran | No suscrito a `messages` | Editar suscripciones de webhook |

---

## 3. Railway (Backend)

**Propósito:** Hosting de APIs y base de datos

### Servicios Activos

| Servicio | Tipo | Descripción |
|----------|------|-------------|
| `homeAssistant-backend` | Web | API principal (auth, admin, finance, subscriptions, calendar) |
| `homeai-assis` | Web | Bot de WhatsApp + Agentes AI |
| `Postgres-Home Asisst` | PostgreSQL | Base de datos compartida |

### Variables de Entorno por Servicio

**homeAssistant-backend (homeai-api):**
```env
DATABASE_URL=postgresql://...
GOOGLE_CLIENT_ID=xxxxxx.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-xxxxxx
JWT_SECRET_KEY=xxxxxx
CORS_ORIGINS=[http://localhost:3000,https://home-assistant-frontend-brown.vercel.app,https://homeai-admin-three.vercel.app]
FRONTEND_URL=https://home-assistant-frontend-brown.vercel.app
MP_ACCESS_TOKEN=APP_USR-xxx-xxx
MP_PUBLIC_KEY=APP_USR-xxx-xxx
MP_WEBHOOK_SECRET=
MP_SANDBOX=true
GITHUB_TOKEN=ghp-xxx
GITHUB_REPO=pablodma/homeAssistant-asistant
GITHUB_BRANCH=master
OPENAI_API_KEY=sk-xxx
```

**homeai-assis:**
```env
DATABASE_URL=postgresql://...
OPENAI_API_KEY=sk-xxxxxx
WHATSAPP_ACCESS_TOKEN=EAAxxxxxx
WHATSAPP_PHONE_NUMBER_ID=967912216407900
WHATSAPP_VERIFY_TOKEN=xxxxxx
BACKEND_API_URL=https://homeassistant-backend-production.up.railway.app
DEFAULT_TENANT_ID=uuid-del-tenant
```

### Comandos Útiles (Railway CLI)

```bash
# Ver proyectos
railway status

# Ver logs de un servicio
railway logs --service homeAssistant-backend

# Ver logs filtrados
railway logs --lines 50 --filter "error"

# Configurar variables
railway variables set KEY=value --service homeAssistant-backend

# Conectar a PostgreSQL
railway connect postgres
```

### Migraciones de Base de Datos

Los scripts de migración están en: `homeai-api/scripts/db/`

```
init.sql                              - Schema inicial (tenants, users, events, reminders, shopping)
002_calendar_google_integration.sql   - Google Calendar OAuth y sync
003_agent_admin.sql                   - Prompts de agentes e interacciones
004_increase_phone_length.sql         - Ampliar campo phone a VARCHAR(100)
005_multitenancy.sql                  - Multi-tenancy dinámico, phone_tenant_mapping
005_1_migrate_current_user.sql        - Migrar datos existentes
006_quality_issues.sql                - Issues de calidad (QA)
007_subscriptions_coupons_pricing.sql - Suscripciones, cupones, pricing de planes
007_qa_reviews.sql                    - Ciclos de revisión QA y prompt revisions
008_plan_services.sql                 - Servicios habilitados por plan
```

**Ejecutar migración:**
```bash
# Opción 1: Railway CLI (si psql está instalado)
railway run psql < scripts/db/007_subscriptions_coupons_pricing.sql

# Opción 2: Script Python
railway run python scripts/run_migration.py scripts/db/008_plan_services.sql
```

---

## 4. Vercel (Frontend)

**Propósito:** Hosting de los frontends Next.js

### Proyectos

| Proyecto | URL | Repo |
|----------|-----|------|
| homeai-web | `https://home-assistant-frontend-brown.vercel.app` | homeAssistant-frontend |
| homeai-admin | `https://homeai-admin-three.vercel.app` | homeAssistant-admin |

### Variables de Entorno (homeai-web)

| Variable | Environment | Valor |
|----------|-------------|-------|
| `GOOGLE_CLIENT_ID` | Production + Preview | `xxxxxx.apps.googleusercontent.com` |
| `GOOGLE_CLIENT_SECRET` | Production + Preview | `GOCSPX-xxxxxx` |
| `NEXTAUTH_SECRET` | Production + Preview | (string aleatorio largo) |
| `NEXTAUTH_URL` | Production | `https://home-assistant-frontend-brown.vercel.app` |
| `NEXT_PUBLIC_API_URL` | Production | `https://homeassistant-backend-production.up.railway.app` |

### Variables de Entorno (homeai-admin)

| Variable | Environment | Valor |
|----------|-------------|-------|
| `GOOGLE_CLIENT_ID` | Production + Preview | (mismo que web) |
| `GOOGLE_CLIENT_SECRET` | Production + Preview | (mismo que web) |
| `NEXTAUTH_SECRET` | Production + Preview | (string aleatorio) |
| `NEXTAUTH_URL` | Production | `https://homeai-admin-three.vercel.app` |
| `NEXT_PUBLIC_API_URL` | Production | `https://homeassistant-backend-production.up.railway.app` |

### Desarrollo Local

**homeai-web** (`.env.local`):
```env
GOOGLE_CLIENT_ID=xxxxxx.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-xxxxxx
NEXTAUTH_SECRET=your-secret-key-here
NEXTAUTH_URL=http://localhost:3000
NEXT_PUBLIC_API_URL=https://homeassistant-backend-production.up.railway.app
```

**homeai-admin** (`.env.local`):
```env
GOOGLE_CLIENT_ID=xxxxxx.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-xxxxxx
NEXTAUTH_SECRET=your-secret-key-here
NEXTAUTH_URL=http://localhost:3001
NEXT_PUBLIC_API_URL=https://homeassistant-backend-production.up.railway.app
```

---

## 5. OpenAI

**Propósito:** Procesamiento de lenguaje natural para los agentes del bot

### Configuración

1. Acceder a https://platform.openai.com/
2. API Keys → Create new secret key
3. Nombre: `homeai-production`

### Variables de Entorno

| Variable | Servicio | Valor |
|----------|----------|-------|
| `OPENAI_API_KEY` | homeai-assis | `sk-xxxxxx` |
| `OPENAI_API_KEY` | homeai-api | `sk-xxxxxx` (para event detection) |

### Modelos Utilizados

- **Router Agent:** `gpt-4o-mini` (clasificación rápida)
- **Finance/Calendar Agents:** `gpt-4o` (tareas complejas)
- **Event Detection:** `gpt-4o-mini` (detección de eventos en el calendario)

### Costos y Límites

- Configurar billing alerts en OpenAI Dashboard
- Considerar rate limiting en el bot (ver TECHNICAL_DEBT.md)

---

## 6. Mercado Pago

**Propósito:** Procesamiento de pagos y suscripciones recurrentes

### Configuración

1. Acceder a https://www.mercadopago.com/developers/
2. Crear aplicación → Tipo: Checkout / Suscripciones
3. Obtener credenciales de prueba (sandbox) o producción

### Credenciales

- **Access Token**: Para operaciones server-side (crear suscripciones, consultar pagos)
- **Public Key**: Para el SDK client-side (no usado actualmente)
- **Webhook Secret**: Para validar webhooks de MP

### Variables de Entorno

| Variable | Servicio | Descripción |
|----------|----------|-------------|
| `MP_ACCESS_TOKEN` | homeai-api | Token de acceso (sandbox o producción) |
| `MP_PUBLIC_KEY` | homeai-api | Clave pública |
| `MP_WEBHOOK_SECRET` | homeai-api | Secret para validar webhooks |
| `MP_SANDBOX` | homeai-api | `true` para sandbox, `false` para producción |
| `FRONTEND_URL` | homeai-api | URL del frontend para redirect post-pago |

### Flujo de Suscripción

```
1. Usuario selecciona plan → Frontend /checkout?plan=family
2. Frontend POST /api/subscriptions → Backend crea preapproval en MP
3. Backend devuelve checkout_url (init_point de MP)
4. Frontend redirige al checkout_url de Mercado Pago
5. Usuario completa pago en MP
6. MP redirige a FRONTEND_URL/checkout/callback con status
7. MP envía webhook a /api/v1/webhooks/mercadopago
8. Backend actualiza subscription status y tenant plan
```

### Requisitos de Mercado Pago

- **Monto mínimo**: $15.00 ARS por suscripción
- **Moneda**: ARS (peso argentino)
- **Frecuencia**: Mensual (configurable)

### Webhooks

Configurar en el dashboard de MP:
- URL: `https://homeassistant-backend-production.up.railway.app/api/v1/webhooks/mercadopago`
- Eventos: `subscription_preapproval`, `payment`

### Errores Comunes

| Error | Causa | Solución |
|-------|-------|----------|
| `Cannot pay an amount lower than $ 15.00` | Precio del plan < $15 ARS | Actualizar precio en admin panel |
| `Invalid value for transaction amount` | Precio es 0 o negativo | Verificar pricing del plan |
| `checkout_url is null` | MP rechazó la creación | Revisar logs del backend |

---

## Checklist de Configuración

### Setup Inicial (nuevo desarrollador)

- [ ] Clonar repositorios (homeai-api, homeai-web, homeai-admin, homeai-assis)
- [ ] Solicitar acceso a Google Cloud Console
- [ ] Solicitar acceso a Meta for Developers
- [ ] Solicitar acceso a Railway (agregar al team)
- [ ] Solicitar acceso a Vercel (agregar al team)
- [ ] Solicitar acceso a Mercado Pago Developers
- [ ] Crear `.env.local` en homeai-web y homeai-admin con todas las variables
- [ ] Crear `.env` en homeai-api con todas las variables
- [ ] Verificar que `npm run dev` funciona en web y admin
- [ ] Verificar login con Google
- [ ] Verificar flujo de checkout (sandbox)

### Rotación de Credenciales

**Cuando renovar:**
- [ ] WhatsApp Access Token (cada 24h si es temporal)
- [ ] OpenAI API Key (si comprometida)
- [ ] JWT Secret (si comprometido)
- [ ] NEXTAUTH_SECRET (si comprometido)
- [ ] MP Access Token (si comprometido o al pasar de sandbox a producción)

**Pasos para rotar:**
1. Generar nueva credencial en el servicio correspondiente
2. Actualizar en Railway/Vercel
3. Actualizar `.env.local` local
4. Redesplegar servicios afectados
5. Verificar funcionamiento

### Verificación Post-Deployment

- [ ] Login con Google funciona (web y admin)
- [ ] Dashboard carga datos
- [ ] Admin panel muestra agentes/interacciones/pricing
- [ ] Flujo de checkout crea suscripción y redirige a MP
- [ ] Enviar mensaje a WhatsApp → Bot responde
- [ ] Interacción aparece en admin

---

## Troubleshooting

### El login falla con error 401

1. Verificar `GOOGLE_CLIENT_ID` en Vercel
2. Verificar URIs de redirección en Google Console
3. Verificar que la app OAuth no fue eliminada

### El bot no responde

1. Verificar logs de `homeai-assis` en Railway
2. Verificar `WHATSAPP_ACCESS_TOKEN` no expiró
3. Verificar webhook está verificado en Meta
4. Verificar `OPENAI_API_KEY` es válido

### Las interacciones no se guardan

1. Verificar conexión a base de datos
2. Verificar `DATABASE_URL` en `homeai-assis`
3. Verificar que las tablas existen (`agent_interactions`)

### Error 500 al hacer login

1. Revisar logs de `homeai-api` en Railway
2. Buscar errores de base de datos
3. Verificar que las migraciones se ejecutaron

### El checkout no redirige a Mercado Pago

1. Verificar `MP_ACCESS_TOKEN` en Railway
2. Verificar que el precio del plan es >= $15 ARS
3. Revisar logs del backend: `railway logs --filter "subscription"`

### Error CORS desde admin

1. Verificar que `CORS_ORIGINS` en Railway incluye la URL del admin
2. Verificar que el backend se deployó correctamente
3. Hard refresh en el browser (Ctrl+Shift+R)

### Los cambios no se reflejan

1. Railway: Verificar que el deploy terminó
2. Vercel: Verificar que el build pasó
3. Limpiar cache del navegador
4. Verificar que las variables de entorno están en el environment correcto

---

## Historial de Cambios de Configuración

| Fecha | Servicio | Cambio | Motivo |
|-------|----------|--------|--------|
| 2026-02-13 | homeai-api | CORS fix + MP error handling | Checkout fallaba silenciosamente |
| 2026-02-12 | homeai-api/web | Mercado Pago inline preapproval | SDK v2 no tiene preapproval_plan |
| 2026-02-12 | homeai-web | Flujo checkout completo | Header → Pricing → Login → Checkout → Onboarding |
| 2026-02-11 | homeai-api | Subscriptions + Coupons | Migration 007, 008 |
| 2026-02-09 | Google OAuth | Nuevas credenciales | App anterior eliminada |
| 2026-02-09 | Railway DB | Migration 004 | Campo phone muy corto |
| 2026-02-09 | homeai-assis | Nuevo Access Token | Token expirado |
| 2026-02-09 | homeai-assis | Nuevo Phone Number ID | Cambio de número de prueba |

---

*Este documento debe mantenerse actualizado cuando se cambie cualquier configuración de servicios externos.*
