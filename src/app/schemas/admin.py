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
]
