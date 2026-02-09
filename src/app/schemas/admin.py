"""Admin schemas for agent management."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from .common import BaseSchema


# =====================================================
# AGENT PROMPTS
# =====================================================


class AgentPromptBase(BaseSchema):
    """Base schema for agent prompts."""

    agent_name: str = Field(..., description="Agent identifier (router, finance, calendar, etc.)")
    prompt_content: str = Field(..., description="The prompt content")


class AgentPromptCreate(AgentPromptBase):
    """Schema for creating a new agent prompt."""

    pass


class AgentPromptUpdate(BaseSchema):
    """Schema for updating an agent prompt."""

    prompt_content: str = Field(..., description="New prompt content")


class AgentPromptResponse(AgentPromptBase):
    """Schema for agent prompt response."""

    id: UUID
    tenant_id: UUID
    version: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class AgentPromptWithDefault(BaseSchema):
    """Schema for agent prompt with default included."""

    agent_name: str
    custom_prompt: Optional[AgentPromptResponse] = None
    default_prompt: str
    is_using_default: bool


class AgentPromptListItem(BaseSchema):
    """Simplified agent prompt for list view."""

    agent_name: str
    version: int
    is_active: bool
    updated_at: datetime
    prompt_preview: str = Field(..., description="First 200 chars of prompt")


class AgentPromptHistory(BaseSchema):
    """Schema for prompt version history."""

    id: UUID
    version: int
    is_active: bool
    created_at: datetime
    prompt_preview: str


# =====================================================
# AGENT INTERACTIONS
# =====================================================


class InteractionResponse(BaseSchema):
    """Schema for interaction log response."""

    id: UUID
    tenant_id: UUID
    user_phone: str
    user_name: Optional[str] = None
    message_in: str
    message_out: str
    agent_used: str
    sub_agent_used: Optional[str] = None
    tokens_in: Optional[int] = None
    tokens_out: Optional[int] = None
    response_time_ms: Optional[int] = None
    created_at: datetime
    metadata: Optional[dict[str, Any]] = None


class InteractionListItem(BaseSchema):
    """Simplified interaction for list view."""

    id: UUID
    user_phone: str
    user_name: Optional[str] = None
    message_preview: str = Field(..., description="First 100 chars of message_in")
    agent_used: str
    sub_agent_used: Optional[str] = None
    response_time_ms: Optional[int] = None
    created_at: datetime


class InteractionListResponse(BaseSchema):
    """Paginated list of interactions."""

    items: list[InteractionListItem]
    total: int
    page: int
    page_size: int
    total_pages: int


class InteractionFilters(BaseSchema):
    """Filters for interaction queries."""

    user_phone: Optional[str] = None
    agent_used: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    search: Optional[str] = None


# =====================================================
# STATISTICS
# =====================================================


class AgentStats(BaseSchema):
    """Statistics for a single agent."""

    agent_name: str
    total_messages: int
    avg_response_time_ms: Optional[float] = None
    total_tokens: int


class DailyStats(BaseSchema):
    """Daily statistics."""

    date: str
    message_count: int
    unique_users: int
    total_tokens: int


class StatsResponse(BaseSchema):
    """Overall statistics response."""

    total_messages: int
    total_users: int
    total_tokens: int
    avg_response_time_ms: Optional[float] = None
    by_agent: list[AgentStats]
    by_day: list[DailyStats]


# =====================================================
# AGENT LIST
# =====================================================


class AgentInfo(BaseSchema):
    """Information about an agent."""

    name: str
    display_name: str
    description: str
    has_prompt: bool
    is_active: bool
    last_updated: Optional[datetime] = None


AGENT_DEFINITIONS = [
    AgentInfo(
        name="router",
        display_name="Router (Orquestador)",
        description="Agente principal que decide qué sub-agente usar",
        has_prompt=False,
        is_active=True,
    ),
    AgentInfo(
        name="finance",
        display_name="Finanzas",
        description="Gestión de gastos y presupuestos",
        has_prompt=False,
        is_active=True,
    ),
    AgentInfo(
        name="calendar",
        display_name="Calendario",
        description="Eventos y sincronización con Google Calendar",
        has_prompt=False,
        is_active=True,
    ),
    AgentInfo(
        name="reminder",
        display_name="Recordatorios",
        description="Recordatorios y alertas",
        has_prompt=False,
        is_active=True,
    ),
    AgentInfo(
        name="shopping",
        display_name="Compras",
        description="Listas de compras",
        has_prompt=False,
        is_active=True,
    ),
    AgentInfo(
        name="vehicle",
        display_name="Vehículos",
        description="Gestión de vehículos y mantenimiento",
        has_prompt=False,
        is_active=True,
    ),
    AgentInfo(
        name="qa",
        display_name="QA (Control de Calidad)",
        description="Analiza interacciones para detectar errores de calidad",
        has_prompt=False,
        is_active=True,
    ),
]


# Default prompts - sync with homeai-assis
DEFAULT_PROMPTS: dict[str, str] = {
    "router": """Agente Orquestador Principal HomeAI. Te llamas Casita.

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
- Si algo no está claro, preguntá antes de asumir
""",
    "finance": """Agente de Finanzas HomeAI.

## Tu Rol

Sos el agente especializado en gestión financiera del hogar. Ayudás a los usuarios a:
- Registrar gastos y transacciones
- Consultar cuánto gastaron
- Ver y gestionar presupuestos
- Analizar patrones de gasto

## Herramientas Disponibles

- **create_expense**: Registrar un gasto nuevo
- **list_expenses**: Ver gastos registrados
- **get_budget**: Ver presupuesto de una categoría
- **set_budget**: Configurar presupuesto

## Tono

- Español argentino informal
- Conciso y práctico
- Confirmá los montos antes de registrar si hay ambigüedad
""",
    "calendar": """Agente de Calendario HomeAI.

## Tu Rol

Sos el agente especializado en gestión de eventos y agenda. Ayudás a los usuarios a:
- Crear y gestionar eventos
- Ver qué tienen programado
- Sincronizar con Google Calendar

## Herramientas Disponibles

- **create_event**: Crear un evento nuevo
- **list_events**: Ver eventos programados
- **delete_event**: Cancelar un evento

## Tono

- Español argentino informal
- Conciso y práctico
""",
    "reminder": """Agente de Recordatorios HomeAI.

## Tu Rol

Sos el agente especializado en recordatorios y alertas. Ayudás a los usuarios a:
- Crear recordatorios
- Ver recordatorios pendientes
- Marcar recordatorios como completados

## Herramientas Disponibles

- **create_reminder**: Crear un recordatorio
- **list_reminders**: Ver recordatorios
- **complete_reminder**: Marcar como completado

## Tono

- Español argentino informal
- Conciso y práctico
""",
    "shopping": """Agente de Compras HomeAI.

## Tu Rol

Sos el agente especializado en listas de compras. Ayudás a los usuarios a:
- Agregar items a la lista
- Ver qué hay que comprar
- Marcar items como comprados

## Herramientas Disponibles

- **add_item**: Agregar item a la lista
- **list_items**: Ver lista de compras
- **mark_purchased**: Marcar como comprado

## Tono

- Español argentino informal
- Conciso y práctico
""",
    "vehicle": """Agente de Vehículos HomeAI.

## Tu Rol

Sos el agente especializado en gestión de vehículos. Ayudás a los usuarios a:
- Registrar services y mantenimiento
- Ver vencimientos (VTV, seguro, patente)
- Consultar historial del vehículo

## Herramientas Disponibles

- **add_service**: Registrar un service
- **list_services**: Ver historial de mantenimiento
- **check_expirations**: Ver vencimientos próximos

## Tono

- Español argentino informal
- Conciso y práctico
""",
    "qa": """Sos un agente de control de calidad para un bot de WhatsApp llamado HomeAI.
Tu trabajo es analizar interacciones y detectar problemas de calidad.

## Tipos de problemas a detectar

1. **misinterpretation**: El bot malinterpretó lo que el usuario quería hacer
   - Ejemplo: Usuario pide "agregar leche" y el bot registra un gasto en vez de agregarlo a la lista

2. **hallucination**: El bot confirmó algo que no hizo o inventó información
   - Ejemplo: Bot dice "Registré el gasto" pero tool_result muestra error
   - Ejemplo: Bot menciona datos que no están en el resultado

3. **unsupported_case**: El usuario pidió algo que el bot no puede hacer
   - Ejemplo: Usuario pide exportar datos a Excel y el bot no tiene esa función
   - Nota: Solo es problema si el bot NO aclara que no puede hacerlo

4. **incomplete_response**: La respuesta está incompleta o falta información importante
   - Ejemplo: Usuario pregunta "cuánto gasté este mes" y bot responde sin dar el total

## Análisis

Evaluá si la respuesta del bot es correcta, útil y honesta.
Considerá especialmente si el bot confirmó acciones que fallaron (hallucination).

## Formato de respuesta

- has_issue: true si detectaste un problema, false si la interacción es correcta
- category: uno de los 4 tipos si has_issue=true, null si has_issue=false
- explanation: explicación breve del problema detectado (en español)
- suggestion: sugerencia de mejora para el prompt o código (en español)
- confidence: qué tan seguro estás del análisis (0.0 a 1.0)
""",
}


def get_default_prompt(agent_name: str) -> str:
    """Get default prompt for an agent."""
    return DEFAULT_PROMPTS.get(agent_name, f"Sos el agente de {agent_name} de HomeAI.")


# =====================================================
# QUALITY ISSUES
# =====================================================


class QualityIssueBase(BaseSchema):
    """Base schema for quality issues."""

    issue_type: str  # 'hard_error', 'soft_error'
    issue_category: str
    error_message: str
    severity: str = "medium"


class QualityIssueResponse(QualityIssueBase):
    """Full quality issue response."""

    id: UUID
    tenant_id: UUID
    interaction_id: Optional[UUID] = None
    user_phone: Optional[str] = None
    agent_name: Optional[str] = None
    tool_name: Optional[str] = None
    message_in: Optional[str] = None
    message_out: Optional[str] = None
    error_code: Optional[str] = None
    qa_analysis: Optional[str] = None
    qa_suggestion: Optional[str] = None
    qa_confidence: Optional[float] = None
    request_payload: Optional[dict[str, Any]] = None
    stack_trace: Optional[str] = None
    correlation_id: Optional[str] = None
    is_resolved: bool = False
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    resolution_notes: Optional[str] = None
    created_at: datetime


class QualityIssueListItem(BaseSchema):
    """Simplified quality issue for list view."""

    id: UUID
    issue_type: str
    issue_category: str
    severity: str
    agent_name: Optional[str] = None
    user_phone: Optional[str] = None
    message_preview: str = Field(..., description="First 100 chars of message_in")
    error_preview: str = Field(..., description="First 150 chars of error_message")
    is_resolved: bool
    created_at: datetime


class QualityIssueListResponse(BaseSchema):
    """Paginated list of quality issues."""

    items: list[QualityIssueListItem]
    total: int
    page: int
    page_size: int
    total_pages: int


class QualityIssueFilters(BaseSchema):
    """Filters for quality issue queries."""

    issue_type: Optional[str] = None  # 'hard_error', 'soft_error'
    issue_category: Optional[str] = None
    severity: Optional[str] = None
    agent_name: Optional[str] = None
    is_resolved: Optional[bool] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class QualityIssueResolve(BaseSchema):
    """Schema for resolving a quality issue."""

    resolution_notes: Optional[str] = None
    resolved_by: Optional[str] = None


class QualityIssueCounts(BaseSchema):
    """Counts of quality issues by type."""

    total: int
    hard_errors: int
    soft_errors: int
    unresolved: int
    by_category: dict[str, int]
    by_severity: dict[str, int]
