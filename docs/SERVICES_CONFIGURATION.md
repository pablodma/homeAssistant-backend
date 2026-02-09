# HomeAI - Guía de Configuración de Servicios Externos

**Última actualización:** 2026-02-09  
**Propósito:** Documentar la configuración necesaria de todos los servicios externos que utiliza HomeAI

---

## Tabla de Contenidos

1. [Arquitectura General](#arquitectura-general)
2. [Google OAuth](#1-google-oauth)
3. [Meta/WhatsApp Business](#2-metawhatsapp-business)
4. [Railway (Backend)](#3-railway-backend)
5. [Vercel (Frontend)](#4-vercel-frontend)
6. [OpenAI](#5-openai)
7. [Checklist de Configuración](#checklist-de-configuración)
8. [Troubleshooting](#troubleshooting)

---

## Arquitectura General

```
┌─────────────────────────────────────────────────────────────────────┐
│                           FRONTEND                                   │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    homeai-web (Vercel)                       │   │
│  │  Next.js 15 + NextAuth + React Query                        │   │
│  │  URL: https://home-assistant-frontend-brown.vercel.app      │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  │ API calls (JWT)
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                            BACKEND                                   │
│  ┌──────────────────────────┐  ┌──────────────────────────────┐    │
│  │ homeai-api (Railway)     │  │ homeai-assis (Railway)        │    │
│  │ FastAPI + PostgreSQL     │  │ FastAPI + LangChain + OpenAI  │    │
│  │ Auth, Admin, Finance     │  │ WhatsApp Webhook + Bot Agents │    │
│  │ Puerto: 8080             │  │ Puerto: 8080                  │    │
│  └──────────────────────────┘  └──────────────────────────────┘    │
│              │                              │                        │
│              │                              │                        │
│              ▼                              ▼                        │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                 PostgreSQL (Railway)                          │  │
│  │         Postgres-Home Asisst (shared database)                │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  │ WhatsApp Messages
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     SERVICIOS EXTERNOS                               │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐        │
│  │  Google OAuth  │  │  Meta/WhatsApp │  │    OpenAI      │        │
│  │  (Login)       │  │  (Messaging)   │  │    (AI)        │        │
│  └────────────────┘  └────────────────┘  └────────────────┘        │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 1. Google OAuth

**Propósito:** Autenticación de usuarios en el panel web

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
   ```
   
   **Authorized redirect URIs:**
   ```
   http://localhost:3000/api/auth/callback/google
   https://home-assistant-frontend-brown.vercel.app/api/auth/callback/google
   ```

5. **Obtener credenciales**
   - Client ID: `xxxxxxxx.apps.googleusercontent.com`
   - Client Secret: `GOCSPX-xxxxxxxxxx`

### Variables de Entorno

| Variable | Ubicación | Valor |
|----------|-----------|-------|
| `GOOGLE_CLIENT_ID` | Vercel (production) | `xxxxxx.apps.googleusercontent.com` |
| `GOOGLE_CLIENT_SECRET` | Vercel (production) | `GOCSPX-xxxxxx` |
| `GOOGLE_CLIENT_ID` | Vercel (development) | (mismo) |
| `GOOGLE_CLIENT_SECRET` | Vercel (development) | (mismo) |
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
- ⚠️ Debe regenerarse cada día

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
| `homeai-api` | Web | API principal (auth, admin, finance) |
| `homeai-assis` | Web | Bot de WhatsApp + Agentes AI |
| `Postgres-Home Asisst` | PostgreSQL | Base de datos compartida |

### Variables de Entorno por Servicio

**homeai-api (homeAssistant-backend):**
```env
DATABASE_URL=postgresql://...
GOOGLE_CLIENT_ID=xxxxxx.apps.googleusercontent.com
JWT_SECRET=xxxxxx
CORS_ORIGINS=https://home-assistant-frontend-brown.vercel.app,http://localhost:3000
```

**homeai-assis:**
```env
DATABASE_URL=postgresql://...
OPENAI_API_KEY=sk-xxxxxx
WHATSAPP_ACCESS_TOKEN=EAAxxxxxx
WHATSAPP_PHONE_NUMBER_ID=967912216407900
WHATSAPP_VERIFY_TOKEN=xxxxxx
BACKEND_API_URL=https://homeai-api-production-xxxx.up.railway.app
DEFAULT_TENANT_ID=uuid-del-tenant
```

### Comandos Útiles (Railway CLI)

```bash
# Ver proyectos
railway status

# Ver logs de un servicio
railway logs --service homeai-assis

# Configurar variables
railway variables set KEY=value --service homeai-assis

# Conectar a PostgreSQL
railway connect postgres
```

### Migraciones de Base de Datos

Los scripts de migración están en: `homeai-api/scripts/db/`

```
001_init.sql          - Schema inicial
002_xxx.sql           - ...
003_agent_admin.sql   - Tablas de agentes e interacciones
004_increase_phone_length.sql - Ampliar campo phone a VARCHAR(100)
```

**Ejecutar migración:**
```bash
# Opción 1: Railway CLI (si psql está instalado)
railway run psql < scripts/db/004_xxx.sql

# Opción 2: Script Node.js temporal
node check_db.js  # (con query de migración)
```

---

## 4. Vercel (Frontend)

**Propósito:** Hosting del frontend Next.js

### Proyecto

- **Nombre:** homeai-web (o similar)
- **URL:** https://home-assistant-frontend-brown.vercel.app
- **Repo:** Conectado a GitHub

### Variables de Entorno

| Variable | Environment | Valor |
|----------|-------------|-------|
| `GOOGLE_CLIENT_ID` | Production + Preview | `xxxxxx.apps.googleusercontent.com` |
| `GOOGLE_CLIENT_SECRET` | Production + Preview | `GOCSPX-xxxxxx` |
| `NEXTAUTH_SECRET` | Production + Preview | (string aleatorio largo) |
| `NEXTAUTH_URL` | Production | `https://home-assistant-frontend-brown.vercel.app` |
| `NEXT_PUBLIC_API_URL` | Production | `https://homeai-api-production-xxxx.up.railway.app` |

### Desarrollo Local

Archivo: `.env.local`
```env
GOOGLE_CLIENT_ID=xxxxxx.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-xxxxxx
NEXTAUTH_SECRET=your-secret-key-here
NEXTAUTH_URL=http://localhost:3000
NEXT_PUBLIC_API_URL=https://homeai-api-production-xxxx.up.railway.app
```

---

## 5. OpenAI

**Propósito:** Procesamiento de lenguaje natural para los agentes

### Configuración

1. Acceder a https://platform.openai.com/
2. API Keys → Create new secret key
3. Nombre: `homeai-production`

### Variables de Entorno

| Variable | Servicio | Valor |
|----------|----------|-------|
| `OPENAI_API_KEY` | homeai-assis | `sk-xxxxxx` |

### Modelos Utilizados

- **Router Agent:** `gpt-4o-mini` (clasificación rápida)
- **Finance/Calendar Agents:** `gpt-4o` (tareas complejas)

### Costos y Límites

- Configurar billing alerts en OpenAI Dashboard
- Considerar rate limiting en el bot (ver TECHNICAL_DEBT.md)

---

## Checklist de Configuración

### Setup Inicial (nuevo desarrollador)

- [ ] Clonar repositorios
- [ ] Solicitar acceso a Google Cloud Console
- [ ] Solicitar acceso a Meta for Developers
- [ ] Solicitar acceso a Railway (agregar al team)
- [ ] Solicitar acceso a Vercel (agregar al team)
- [ ] Crear `.env.local` con todas las variables
- [ ] Verificar que `npm run dev` funciona
- [ ] Verificar login con Google

### Rotación de Credenciales

**Cuando renovar:**
- [ ] WhatsApp Access Token (cada 24h si es temporal)
- [ ] OpenAI API Key (si comprometida)
- [ ] JWT Secret (si comprometido)
- [ ] NEXTAUTH_SECRET (si comprometido)

**Pasos para rotar:**
1. Generar nueva credencial en el servicio correspondiente
2. Actualizar en Railway/Vercel
3. Actualizar `.env.local` local
4. Redesplegar servicios afectados
5. Verificar funcionamiento

### Verificación Post-Deployment

- [ ] Login con Google funciona
- [ ] Dashboard carga datos
- [ ] Admin panel muestra agentes/interacciones
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

### Los cambios no se reflejan

1. Railway: Verificar que el deploy terminó
2. Vercel: Verificar que el build pasó
3. Limpiar cache del navegador
4. Verificar que las variables de entorno están en el environment correcto

---

## Historial de Cambios de Configuración

| Fecha | Servicio | Cambio | Motivo |
|-------|----------|--------|--------|
| 2026-02-09 | Google OAuth | Nuevas credenciales | App anterior eliminada |
| 2026-02-09 | Railway DB | Migration 004 | Campo phone muy corto |
| 2026-02-09 | homeai-assis | Nuevo Access Token | Token expirado |
| 2026-02-09 | homeai-assis | Nuevo Phone Number ID | Cambio de número de prueba |

---

*Este documento debe mantenerse actualizado cuando se cambie cualquier configuración de servicios externos.*
