# HomeAI - Deuda Técnica y Roadmap a Producción

**Última actualización:** 2026-02-09 (auth + WhatsApp + DB migration)  
**Estado actual:** Fase 2 (MVP)

---

## Resumen Ejecutivo

Este documento mapea todo lo que es necesario y deseable tener antes de salir a producción con HomeAI Assistant. Se organiza en:
- **P0 (Crítico)**: Bloquea producción, debe hacerse sí o sí
- **P1 (Importante)**: Muy recomendado para producción estable
- **P2 (Deseable)**: Nice-to-have, puede hacerse post-lanzamiento

---

## 🔴 P0 - CRÍTICO (Bloquea Producción)

### 1. Multi-tenant Real
**Estado:** Parcialmente implementado  
**Ubicación:** `homeai-assis`, `homeai-api`

**Problema:**
- Actualmente el bot usa `DEFAULT_TENANT_ID` fijo del .env
- No hay mapeo teléfono → tenant
- Múltiples hogares no pueden usar el bot simultáneamente

**Solución requerida:**
```
1. Crear tabla phone_tenant_mapping:
   - phone_number (unique)
   - tenant_id (FK)
   - user_id (FK)
   - created_at
   
2. Flujo de asociación:
   - Si phone no existe → crear tenant nuevo o solicitar vinculación
   - Si phone existe → usar tenant asociado
   
3. Actualizar RouterAgent para obtener tenant_id dinámicamente
```

**Esfuerzo estimado:** 2-3 días

---

### 2. Manejo de Errores del Bot
**Estado:** Básico  
**Ubicación:** `homeai-assis/src/app/agents/`

**Problema:**
- Si el bot falla, el usuario no recibe respuesta
- No hay retry logic
- Errores de OpenAI no se manejan gracefully

**Solución requerida:**
```python
# Cada agente debe:
1. Capturar excepciones y enviar mensaje de error amigable
2. Implementar retry con exponential backoff para OpenAI
3. Timeout máximo de 25 segundos (WhatsApp timeout ~30s)
4. Logging estructurado de todos los errores
```

**Código faltante:**
```python
# En base.py
async def process_with_fallback(self, message: str) -> str:
    try:
        return await self.process(message)
    except OpenAIError as e:
        logger.error("openai_error", error=str(e))
        return "Hubo un problema procesando tu mensaje. Intentá de nuevo en unos segundos."
    except Exception as e:
        logger.exception("agent_error", error=str(e))
        return "Algo salió mal. Por favor intentá de nuevo."
```

**Esfuerzo estimado:** 1-2 días

---

### 3. Validación de Webhook Signature
**Estado:** NO implementado  
**Ubicación:** `homeai-assis/src/app/whatsapp/webhook.py`

**Problema:**
- El webhook acepta cualquier request sin validar que viene de Meta
- Riesgo de seguridad: cualquiera puede enviar requests falsos

**Solución requerida:**
```python
import hmac
import hashlib

def verify_webhook_signature(payload: bytes, signature: str, app_secret: str) -> bool:
    expected = hmac.new(
        app_secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)

# En el router:
@router.post("/webhook")
async def webhook(request: Request):
    signature = request.headers.get("X-Hub-Signature-256", "")
    body = await request.body()
    
    if not verify_webhook_signature(body, signature, settings.whatsapp_app_secret):
        raise HTTPException(status_code=401, detail="Invalid signature")
    # ...
```

**Variable de entorno nueva:** `WHATSAPP_APP_SECRET`

**Esfuerzo estimado:** 0.5 días

---

### 4. Rate Limiting
**Estado:** NO implementado  
**Ubicación:** `homeai-assis`, `homeai-api`

**Problema:**
- Sin límites, un usuario puede saturar el servicio
- Costos de OpenAI pueden dispararse
- Posible abuso o ataques

**Solución requerida:**
```python
# Límites sugeridos:
- 30 mensajes por usuario por hora
- 100 mensajes por tenant por hora
- 1000 tokens por mensaje (truncar si excede)

# Implementación con Redis o in-memory cache
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter

@router.post("/webhook")
async def webhook(
    request: Request,
    _: None = Depends(RateLimiter(times=30, hours=1))
):
```

**Esfuerzo estimado:** 1 día

---

### 5. Health Checks Completos
**Estado:** Básico  
**Ubicación:** `homeai-assis/src/app/main.py`

**Problema:**
- Health check actual solo verifica que el proceso corre
- No verifica conexión a DB, OpenAI, Backend API

**Solución requerida:**
```python
@app.get("/health")
async def health():
    checks = {
        "database": await check_database(),
        "openai": await check_openai(),
        "backend": await check_backend(),
    }
    
    all_healthy = all(checks.values())
    status_code = 200 if all_healthy else 503
    
    return JSONResponse(
        status_code=status_code,
        content={"status": "healthy" if all_healthy else "unhealthy", "checks": checks}
    )
```

**Esfuerzo estimado:** 0.5 días

---

## 🟡 P1 - IMPORTANTE (Muy Recomendado)

### 6. Tests Automatizados
**Estado:** Mínimo  
**Ubicación:** Todos los repos

**Problema:**
- Solo hay test de health básico
- No hay tests de agentes
- No hay tests de integración
- Difícil detectar regresiones

**Solución requerida:**
```
Tests necesarios:
├── homeai-assis/
│   ├── test_router_agent.py      # Routing correcto
│   ├── test_finance_agent.py     # Parsing de gastos
│   ├── test_webhook.py           # Manejo de payloads
│   └── test_conversation.py      # Memoria de chat
├── homeai-api/
│   ├── test_admin_endpoints.py   # CRUD admin
│   ├── test_finance_endpoints.py # API finance
│   └── test_tenant_isolation.py  # Multi-tenancy
└── homeai-web/
    └── test_admin_components.tsx # Componentes admin
```

**Esfuerzo estimado:** 3-5 días

---

### 7. Logging Estructurado
**Estado:** Parcial  
**Ubicación:** `homeai-assis`

**Problema:**
- Logs no estructurados dificultan debugging
- No hay correlation IDs entre servicios
- Difícil rastrear un mensaje end-to-end

**Solución requerida:**
```python
# Agregar request_id a cada mensaje
import structlog
from uuid import uuid4

logger = structlog.get_logger()

async def process_message(message: IncomingMessage):
    request_id = str(uuid4())
    log = logger.bind(
        request_id=request_id,
        user_phone=message.sender,
        tenant_id=tenant_id
    )
    
    log.info("message_received", content=message.content[:50])
    # ... proceso ...
    log.info("message_sent", agent=agent_used, response_time_ms=elapsed)
```

**Esfuerzo estimado:** 1 día

---

### 8. Monitoreo y Alertas
**Estado:** NO implementado  
**Ubicación:** Railway/Vercel + servicio externo

**Problema:**
- No hay alertas cuando el servicio falla
- No hay métricas de uso
- Problemas se detectan cuando el usuario reporta

**Solución requerida:**
```
Opciones:
1. Railway Metrics + PagerDuty/Opsgenie
2. Sentry para error tracking
3. Datadog/New Relic para APM

Alertas mínimas:
- Error rate > 5% en 5 minutos
- Response time > 5 segundos
- Service down por > 1 minuto
- Token usage > threshold diario
```

**Esfuerzo estimado:** 1-2 días (setup inicial)

---

### 9. Documentación de API
**Estado:** NO existe  
**Ubicación:** `homeai-api/docs/`

**Problema:**
- No hay OpenAPI spec actualizado
- Difícil para otros devs entender la API
- No hay ejemplos de uso

**Solución requerida:**
```yaml
# Generar desde FastAPI:
# GET /docs → Swagger UI
# GET /openapi.json → Spec JSON

# Exportar y versionar:
homeai-api/docs/
├── openapi.yaml       # Spec completa
├── api-guide.md       # Guía de uso
└── postman/           # Collection para testing
```

**Esfuerzo estimado:** 1 día

---

### 10. Backup y Recovery
**Estado:** NO implementado  
**Ubicación:** Railway PostgreSQL

**Problema:**
- No hay backups automáticos configurados
- No hay plan de disaster recovery
- Pérdida de datos = pérdida total

**Solución requerida:**
```
1. Railway automatic backups (verificar que estén activos)
2. Script de backup manual a S3/GCS
3. Documentar proceso de restore
4. Probar restore al menos 1 vez
```

**Esfuerzo estimado:** 0.5-1 día

---

## 🟢 P2 - DESEABLE (Nice-to-Have)

### 11. Recordatorios Proactivos
**Estado:** NO implementado  
**Ubicación:** `homeai-assis`

**Problema:**
- Los recordatorios se guardan pero nunca se envían
- WhatsApp requiere templates aprobados para iniciar conversaciones

**Solución requerida:**
```
1. Crear template en Meta Business:
   "Hola {{1}}, recordatorio: {{2}}"
   
2. Worker que corre cada minuto:
   - Buscar recordatorios con due_at <= now
   - Enviar usando template
   - Marcar como sent
   
3. Manejar ventana de 24h de WhatsApp
```

**Esfuerzo estimado:** 2-3 días (incluyendo aprobación de Meta)

---

### 12. Caché de Respuestas
**Estado:** NO implementado  
**Ubicación:** `homeai-assis`

**Problema:**
- Cada mensaje va a OpenAI aunque sea repetido
- Costo innecesario en queries frecuentes

**Solución requerida:**
```python
# Cachear respuestas para queries tipo:
# - "Cuánto gasté este mes?" (cache 5 min)
# - "Qué tengo en la lista?" (cache 1 min)

# Usar Redis o in-memory cache con TTL
```

**Esfuerzo estimado:** 1 día

---

### 13. Optimización de Prompts
**Estado:** Básico  
**Ubicación:** `homeai-assis/src/app/agents/`

**Problema:**
- Prompts actuales son largos y consumen muchos tokens
- No hay métricas de efectividad por prompt

**Solución requerida:**
```
1. Analizar logs de interacciones
2. Identificar patrones de routing incorrecto
3. Optimizar prompts para reducir tokens
4. A/B testing de prompts via versionado
```

**Esfuerzo estimado:** 2-3 días (iterativo)

---

### 14. Frontend Admin Completo
**Estado:** Funcional pero básico  
**Ubicación:** `homeai-web/src/app/(admin)/`

**Mejoras deseables:**
- [ ] Gráficos de estadísticas más detallados
- [ ] Export de datos a CSV
- [ ] Búsqueda avanzada en interacciones
- [ ] Dark mode
- [ ] Mobile responsive completo

**Esfuerzo estimado:** 3-5 días

---

### 15.1. Sincronización de Autenticación en Hooks de Finance
**Estado:** Parcial  
**Ubicación:** `homeai-web/src/features/finance/hooks.ts`

**Problema:**
- Los hooks de finance no tienen `enabled` condicionado a `isAuthenticated`
- Aunque actualmente funcionan porque se pasa `tenantId` manualmente, podrían tener el mismo problema de timing si se llaman antes de que el token esté configurado
- Inconsistencia con el patrón establecido en hooks de admin

**Solución requerida:**
```typescript
// Opción 1: Agregar isAuthenticated a cada hook
export function useBudgets(tenantId: string, options?) {
  const { isAuthenticated } = useApiAuth();
  
  return useQuery({
    queryKey: financeKeys.budgets(tenantId),
    queryFn: () => financeApi.getBudgets(tenantId),
    enabled: isAuthenticated && !!tenantId,
    ...options,
  });
}

// Opción 2: Crear wrapper hook que valide autenticación
export function useAuthenticatedQuery<T>(options: UseQueryOptions<T>) {
  const { isAuthenticated } = useApiAuth();
  return useQuery({
    ...options,
    enabled: isAuthenticated && (options.enabled ?? true),
  });
}
```

**Esfuerzo estimado:** 0.5 días

---

### 15. Onboarding Self-Service
**Estado:** NO implementado  
**Ubicación:** `homeai-web`

**Problema:**
- Nuevos tenants se crean manualmente
- No hay flujo para vincular WhatsApp

**Solución requerida:**
```
1. Página de registro público
2. Flujo de verificación de WhatsApp:
   - Usuario ingresa su número
   - Bot envía código de verificación
   - Usuario confirma código en web
3. Creación automática de tenant
```

**Esfuerzo estimado:** 3-4 días

---

## Resumen por Servicio

### homeai-assis (Bot)
| Item | Prioridad | Estado | Esfuerzo |
|------|-----------|--------|----------|
| Multi-tenant real | P0 | Parcial | 2-3 días |
| Manejo de errores | P0 | Básico | 1-2 días |
| Validación webhook | P0 | NO | 0.5 días |
| Rate limiting | P0 | NO | 1 día |
| Health checks | P0 | Básico | 0.5 días |
| Tests | P1 | Mínimo | 2-3 días |
| Logging | P1 | Parcial | 1 día |
| Recordatorios | P2 | NO | 2-3 días |
| Caché | P2 | NO | 1 día |

### homeai-api (Backend)
| Item | Prioridad | Estado | Esfuerzo |
|------|-----------|--------|----------|
| Tests | P1 | Mínimo | 2 días |
| Documentación API | P1 | NO | 1 día |
| Backup | P1 | ? | 0.5 días |

### homeai-web (Frontend)
| Item | Prioridad | Estado | Esfuerzo |
|------|-----------|--------|----------|
| Tests | P1 | NO | 1-2 días |
| Admin mejorado | P2 | Básico | 3-5 días |
| Onboarding | P2 | NO | 3-4 días |
| Sync auth hooks finance | P2 | Parcial | 0.5 días |
| ~~Timing auth admin~~ | ~~P0~~ | ~~RESUELTO~~ | ~~-~~ |

### Infraestructura
| Item | Prioridad | Estado | Esfuerzo |
|------|-----------|--------|----------|
| Monitoreo/Alertas | P1 | NO | 1-2 días |
| CI/CD tests | P1 | NO | 1 día |

---

## Plan de Acción Sugerido

### Sprint 1 (1 semana) - Críticos
1. ✅ Validación webhook signature
2. ✅ Manejo de errores robusto
3. ✅ Rate limiting básico
4. ✅ Health checks completos

### Sprint 2 (1 semana) - Multi-tenant
1. Tabla phone_tenant_mapping
2. Flujo de asociación
3. Testing de aislamiento

### Sprint 3 (1 semana) - Estabilidad
1. Tests automatizados core
2. Monitoreo y alertas
3. Documentación API
4. Backup verificado

### Post-lanzamiento
- Recordatorios proactivos
- Optimización de prompts
- Mejoras de admin
- Onboarding self-service

---

## ✅ Problemas Resueltos

### [2026-02-09] Error fijar_presupuesto - Columna updated_at inexistente

**Síntoma:**
- Al intentar fijar un presupuesto via WhatsApp ("quiero fijar un presupuesto de 500.000 en supermercado mensual"), el bot respondía con error
- El tool call se ejecutaba correctamente pero el backend fallaba

**Causa raíz:**
```
asyncpg.exceptions.UndefinedColumnError: column "updated_at" of relation "budget_categories" does not exist
```

La función `update_budget_category` en `finance.py` intentaba setear `updated_at = NOW()`, pero la tabla `budget_categories` no tiene esa columna.

**Solución:**
Removida la línea que intentaba actualizar `updated_at` en `homeai-api/src/app/repositories/finance.py`:

```python
# Antes (línea 321):
set_parts.append("updated_at = NOW()")

# Después:
# Note: budget_categories table doesn't have updated_at column
```

**Archivos modificados:**
- `homeai-api/src/app/repositories/finance.py` - Removida referencia a `updated_at`

**Verificación:**
- ✅ Tool `fijar_presupuesto` funciona correctamente
- ✅ Presupuestos se crean/actualizan sin error

---

### [2026-02-09] Error 401 Unauthorized - Google OAuth + DB Schema + WhatsApp Token

**Síntomas reportados:**
- Al visitar `/admin` después de loguearse, todas las llamadas API fallaban con 401 Unauthorized
- Los agentes, interacciones y estadísticas no se mostraban
- El bot de WhatsApp no guardaba interacciones en la base de datos

**Investigación y hallazgos (en orden cronológico):**

1. **Google OAuth Client eliminado**
   - Error inicial: `401: deleted_client` al intentar login con Google
   - Causa: Las credenciales de Google OAuth (`GOOGLE_CLIENT_ID`) correspondían a una app eliminada en Google Cloud Console

2. **Campo phone VARCHAR(20) muy corto**
   - Error: `500 Internal Server Error` del backend al intercambiar token
   - Log: `asyncpg.exceptions.StringDataRightTruncationError: value too long for type character varying(20)`
   - Causa: El código insertaba `oauth:pabloignacio.d@gmail.com` (27 chars) en campo `phone VARCHAR(20)`
   - El campo phone estaba diseñado para números telefónicos, no para placeholder de OAuth users

3. **WhatsApp Access Token expirado**
   - Error: `Session has expired on Sunday, 08-Feb-26 16:00:00 PST`
   - Causa: Los tokens temporales de WhatsApp expiran cada 24 horas

4. **Número de WhatsApp cambiado**
   - El número de prueba de WhatsApp Business fue cambiado, requiriendo actualizar `WHATSAPP_PHONE_NUMBER_ID`

**Soluciones implementadas:**

1. **Nuevas credenciales de Google OAuth**
   ```
   Ubicación: Google Cloud Console → APIs & Services → Credentials
   
   Variables actualizadas:
   - Railway (homeAssistant-backend): GOOGLE_CLIENT_ID
   - Vercel (production + development): GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET
   - Local (.env.local): GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET
   
   URIs de redirección configuradas:
   - http://localhost:3000/api/auth/callback/google
   - https://home-assistant-frontend-brown.vercel.app/api/auth/callback/google
   ```

2. **Migración de base de datos**
   ```sql
   -- Archivo: homeai-api/scripts/db/004_increase_phone_length.sql
   ALTER TABLE users ALTER COLUMN phone TYPE VARCHAR(100);
   
   -- Ejecutado directamente en Railway PostgreSQL (Postgres-Home Asisst)
   -- Host: nozomi.proxy.rlwy.net:25188
   ```

3. **Actualización de tokens de WhatsApp**
   ```
   Variables en Railway (homeai-assis):
   - WHATSAPP_ACCESS_TOKEN: Token actualizado desde Meta for Developers
   - WHATSAPP_PHONE_NUMBER_ID: 967912216407900 (nuevo número de prueba)
   ```

**Archivos modificados:**
- `homeai-api/scripts/db/004_increase_phone_length.sql` (nuevo)
- Variables de entorno en Railway y Vercel

**Lecciones aprendidas:**
1. Los tokens temporales de WhatsApp expiran cada 24h - considerar tokens permanentes para producción
2. Los esquemas de DB deben contemplar casos de uso OAuth desde el inicio
3. Tener un checklist de configuración de servicios externos documentado
4. Los errores 500 del backend pueden ocultar errores de DB - siempre revisar logs del servidor

**Verificación:**
- ✅ Login con Google funciona
- ✅ Panel de admin muestra datos
- ✅ Bot de WhatsApp responde mensajes
- ✅ Interacciones se guardan en la base de datos

---

### [2026-02-08] Timing de Autenticación en Admin Panel
**Problema:**
- Al navegar de `/dashboard` a `/admin`, las llamadas API fallaban con 401 Unauthorized
- Los queries de React Query se disparaban antes de que el `useEffect` del `ApiProvider` configurara el token de autenticación
- `/dashboard` es Server Component (no hace llamadas API client-side), `/admin` es Client Component con múltiples queries

**Causa raíz:**
- El `ApiProvider` usaba `useEffect` para sincronizar el token, pero los queries de React Query se ejecutaban inmediatamente al montar los componentes
- El `useEffect` no se había ejecutado aún cuando los queries se disparaban

**Solución implementada:**
```typescript
// 1. Agregado Context en api-provider.tsx con estado de autenticación
interface ApiContextValue {
  isReady: boolean;
  isAuthenticated: boolean;
}

// 2. Hook useApiAuth() para verificar disponibilidad del token
export function useApiAuth() {
  return useContext(ApiContext);
}

// 3. Todos los hooks de admin ahora usan enabled: isAuthenticated
export function useAgents() {
  const { isAuthenticated } = useApiAuth();
  return useQuery({
    queryKey: ['admin', 'agents'],
    queryFn: getAgents,
    enabled: isAuthenticated,  // ← Espera al token
  });
}
```

**Archivos modificados:**
- `homeai-web/src/lib/api-provider.tsx` - Agregado Context y hook `useApiAuth`
- `homeai-web/src/features/admin/hooks.ts` - Todos los hooks usan `enabled: isAuthenticated`

**Lección aprendida:**
- Cuando se usa un cliente API singleton con autenticación asíncrona, los queries deben esperar a que la autenticación esté lista
- El patrón de `enabled` en React Query es la forma correcta de manejar dependencias asíncronas

---

## Notas Finales

**Criterio de "Listo para Producción":**
- Todos los P0 completados
- Al menos 50% de P1 completados
- Tests de aislamiento multi-tenant pasando
- Monitoreo básico funcionando
- Backup verificado

**Riesgos principales:**
1. Multi-tenant mal implementado → data leak entre hogares
2. Sin rate limiting → costos de OpenAI explosivos
3. Sin validación webhook → posibles ataques
4. Sin monitoreo → problemas no detectados

---

*Este documento debe actualizarse a medida que se completan items.*
