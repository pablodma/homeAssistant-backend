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


class PromptUpdateResponse(BaseSchema):
    """Response after updating a prompt via GitHub API."""

    agent_name: str
    commit_sha: str = Field(..., description="Git commit SHA")
    commit_url: str = Field(..., description="URL to view the commit on GitHub")
    file_url: str = Field(..., description="URL to view the file on GitHub")
    message: str = Field(
        default="Prompt actualizado. El cambio se desplegará en ~30 segundos.",
        description="Success message",
    )


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
        name="subscription",
        display_name="Suscripciones",
        description="Onboarding WhatsApp y gestión de suscripciones (planes, upgrade, cancelación)",
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
    AgentInfo(
        name="qa-reviewer",
        display_name="QA Reviewer (Mejora Continua)",
        description="Analiza issues acumulados y propone mejoras en prompts de agentes",
        has_prompt=False,
        is_active=True,
    ),
]


# Mapping of agent names to their prompt files
# Prompts live in docs/prompts/ - single source of truth
PROMPT_FILES = {
    "router": "router-agent.md",
    "finance": "finance-agent.md",
    "calendar": "calendar-agent.md",
    "reminder": "reminder-agent.md",
    "shopping": "shopping-agent.md",
    "vehicle": "vehicle-agent.md",
    "subscription": "subscription-agent.md",
    "qa": "qa-agent.md",
    "qa-reviewer": "qa-reviewer-agent.md",
}


def get_default_prompt(agent_name: str) -> str:
    """Get prompt for an agent from configuration files.
    
    Prompts are read-only in admin panel. To modify:
    1. Edit docs/prompts/{agent}-agent.md
    2. Commit + push
    3. Redeploy
    
    This ensures single source of truth and version control.
    """
    from pathlib import Path
    
    if agent_name not in PROMPT_FILES:
        return f"Sos el agente de {agent_name} de HomeAI."
    
    prompts_dir = Path(__file__).parent.parent.parent.parent / "docs" / "prompts"
    prompt_path = prompts_dir / PROMPT_FILES[agent_name]
    
    try:
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")
    except Exception:
        pass
    
    return f"[Prompt no encontrado para {agent_name}. Verificar docs/prompts/{PROMPT_FILES[agent_name]}]"


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
    admin_insight: Optional[str] = None
    fix_status: Optional[str] = None
    fix_error: Optional[str] = None
    fix_result: Optional[dict[str, Any]] = None
    created_at: datetime
    related_issues: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Other issues from the same interaction (linked by interaction_id)",
    )


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


class QualityIssueInsightUpdate(BaseSchema):
    """Schema for updating admin insight on a quality issue."""

    admin_insight: str = Field(..., description="Admin's analysis/insight for this issue")


class ApplyFixResponse(BaseSchema):
    """Response from requesting a fix (async - returns immediately)."""

    status: str = "accepted"
    issue_id: str
    message: str = "Fix iniciado. El estado se actualiza automáticamente."


# =====================================================
# QA REVIEW
# =====================================================


class QAReviewRequest(BaseSchema):
    """Request to trigger a QA review."""

    days: int = Field(30, ge=1, le=365, description="How many days back to analyze")


class PromptRevisionItem(BaseSchema):
    """A single prompt revision from a review cycle."""

    revision_id: str
    agent_name: str
    improvement_reason: str
    changes_summary: list[dict[str, Any]] = []
    confidence: float = 0.0
    github_commit_sha: str = ""
    github_commit_url: str = ""
    is_rolled_back: bool = False


class QAReviewResponse(BaseSchema):
    """Response from a QA review execution."""

    cycle_id: str
    status: str  # 'completed', 'failed'
    issues_analyzed: int
    improvements_applied: int
    analysis: Optional[dict[str, Any]] = None  # parsed XML sections
    revisions: list[PromptRevisionItem] = []
    message: Optional[str] = None


class QAReviewHistoryItem(BaseSchema):
    """Summary of a past QA review cycle."""

    id: UUID
    triggered_by: str
    period_start: datetime
    period_end: datetime
    issues_analyzed_count: int
    improvements_applied_count: int
    status: str
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    analysis_result: Optional[dict[str, Any]] = None
    revisions: list[dict[str, Any]] = []


class RollbackResponse(BaseSchema):
    """Response from rolling back a prompt revision."""

    revision_id: str
    agent_name: str
    commit_sha: str
    commit_url: str
