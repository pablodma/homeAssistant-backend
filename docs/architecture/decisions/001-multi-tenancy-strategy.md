# ADR-001: Estrategia de Multi-tenancy

## Estado
**Aceptado** - 2026-02-07

## Contexto

HomeAI Assistant es un sistema SaaS donde múltiples organizaciones (tenants) comparten la misma infraestructura pero deben tener sus datos completamente aislados. Un solo número de WhatsApp sirve a todos los tenants.

### Requisitos
1. Aislamiento completo de datos entre tenants
2. Escalabilidad para cientos de tenants inicialmente
3. Simplicidad operativa (migraciones, backups, monitoreo)
4. Costo de infraestructura razonable para MVP
5. Capacidad de auditar acceso a datos por tenant

### Opciones Evaluadas

#### Opción A: Database por Tenant
```
tenant_1_db ─── PostgreSQL Instance 1
tenant_2_db ─── PostgreSQL Instance 2
tenant_n_db ─── PostgreSQL Instance N
```

**Pros**:
- Aislamiento físico completo
- Fácil de cumplir regulaciones estrictas
- Performance predecible por tenant

**Contras**:
- Costo de infraestructura alto (N databases)
- Complejidad operativa extrema (N migraciones, N backups)
- Connection pooling complejo
- No viable para MVP

#### Opción B: Schema por Tenant
```
PostgreSQL Instance
├── schema_tenant_1
├── schema_tenant_2
└── schema_tenant_n
```

**Pros**:
- Aislamiento lógico fuerte
- Una sola instancia de DB
- Migraciones más simples que DB por tenant

**Contras**:
- Límite de schemas en PostgreSQL (~10,000)
- Complejidad en queries cross-tenant (analytics)
- Connection pooling por schema
- Tooling de ORM más complejo

#### Opción C: Shared Tables con tenant_id (Elegida)
```
PostgreSQL Instance
├── expenses (tenant_id, ...)
├── events (tenant_id, ...)
└── ... todas las tablas con tenant_id
```

**Pros**:
- Simplicidad operativa máxima
- Una sola migración aplica a todos
- Queries simples con WHERE tenant_id = X
- Connection pooling trivial
- Funciona bien con asyncpg (solo agregar filtro `WHERE tenant_id = $X`)
- Escalable horizontalmente (read replicas)

**Contras**:
- Riesgo de leak si se olvida el filtro
- Performance puede degradar con muchos tenants (mitigable con índices)
- Row Level Security añade overhead

## Decisión

**Elegimos Opción C: Shared Tables con `tenant_id`**

### Implementación

1. **Todas las tablas** con datos de negocio incluyen columna `tenant_id UUID NOT NULL`

2. **Índices compuestos** con `tenant_id` como primer campo:
   ```sql
   CREATE INDEX idx_expenses_tenant_date ON expenses(tenant_id, expense_date);
   ```

3. **Constraints únicos** incluyen tenant_id:
   ```sql
   UNIQUE(tenant_id, idempotency_key)
   UNIQUE(tenant_id, name) -- para categorías, listas, etc.
   ```

4. **Row Level Security** como capa adicional (opcional pero recomendado):
   ```sql
   ALTER TABLE expenses ENABLE ROW LEVEL SECURITY;
   CREATE POLICY tenant_isolation ON expenses
       USING (tenant_id = current_setting('app.current_tenant')::uuid);
   ```

5. **Toda query** DEBE incluir filtro por tenant:
   ```sql
   -- CORRECTO
   SELECT * FROM expenses WHERE tenant_id = $1 AND expense_date = $2;
   
   -- INCORRECTO (nunca hacer)
   SELECT * FROM expenses WHERE expense_date = $2;
   ```

### Mitigaciones de Riesgo

| Riesgo | Mitigación |
|--------|------------|
| Olvidar filtro tenant_id | Code review, RLS como backup, tests automatizados |
| Query lenta con muchos tenants | Índices con tenant_id primero, EXPLAIN ANALYZE |
| Leak en logs | Sanitizar logs, no loggear datos sensibles |
| Acceso cross-tenant malicioso | Audit logs, alertas por patrones anómalos |

### Validación en el Código

En cada repository (asyncpg):
```python
# Toda query DEBE incluir tenant_id
async def get_expenses(tenant_id: UUID, ...):
    query = """
        SELECT * FROM expenses 
        WHERE tenant_id = $1 
        AND expense_date >= $2
    """
    async with pool.acquire() as conn:
        return await conn.fetch(query, tenant_id, start_date)
```

En los agentes de homeai-assis:
```python
# El tenant_id se resuelve desde phone_tenant_mapping
tenant_id = await get_tenant_from_phone(phone_number)
if not tenant_id:
    raise ValueError("No tenant associated with this phone number")
```

## Consecuencias

### Positivas
- Setup inicial simple
- Migraciones atómicas para todos los tenants
- Fácil de implementar con asyncpg y repositorios Python
- Bajo costo de infraestructura
- Escalable con read replicas

### Negativas
- Requiere disciplina en filtrar por tenant_id
- Analytics cross-tenant requiere cuidado
- RLS añade pequeño overhead de CPU

### Neutras
- Límite práctico de ~10,000 tenants activos por instancia (suficiente para MVP y más allá)

## Referencias

- [PostgreSQL Row Level Security](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)
- [Multi-tenant SaaS patterns](https://docs.microsoft.com/en-us/azure/sql-database/saas-tenancy-app-design-patterns)
- [Railway PostgreSQL](https://docs.railway.app/databases/postgresql)
