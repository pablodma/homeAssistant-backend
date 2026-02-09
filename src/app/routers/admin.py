"""Admin router for agent management."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from ..middleware.auth import get_current_user
from ..schemas.admin import (
    AgentInfo,
    AgentPromptHistory,
    AgentPromptResponse,
    AgentPromptUpdate,
    AgentPromptWithDefault,
    InteractionListResponse,
    InteractionResponse,
    QualityIssueCounts,
    QualityIssueListResponse,
    QualityIssueResolve,
    QualityIssueResponse,
    StatsResponse,
    get_default_prompt,
)
from ..schemas.auth import CurrentUser
from ..services.admin import AdminService

router = APIRouter(prefix="/tenants/{tenant_id}/admin", tags=["Admin"])


def get_admin_service() -> AdminService:
    """Get admin service instance."""
    return AdminService()


# =====================================================
# AGENTS
# =====================================================


@router.get("/agents", response_model=list[AgentInfo])
async def list_agents(
    tenant_id: UUID,
    service: AdminService = Depends(get_admin_service),
    _: CurrentUser = Depends(get_current_user),
) -> list[AgentInfo]:
    """List all available agents with their status.

    Returns information about each agent including whether it has a custom
    prompt configured and when it was last updated.
    """
    return await service.get_agents(str(tenant_id))


# =====================================================
# PROMPTS
# =====================================================


@router.get("/agents/{agent_name}/prompt", response_model=AgentPromptWithDefault)
async def get_agent_prompt(
    tenant_id: UUID,
    agent_name: str,
    service: AdminService = Depends(get_admin_service),
    _: CurrentUser = Depends(get_current_user),
) -> AgentPromptWithDefault:
    """Get the active prompt for an agent.

    Returns the current active prompt content and metadata,
    along with the default prompt for reference.
    """
    custom_prompt = await service.get_prompt(str(tenant_id), agent_name)
    default_prompt = get_default_prompt(agent_name)
    
    return AgentPromptWithDefault(
        agent_name=agent_name,
        custom_prompt=custom_prompt,
        default_prompt=default_prompt,
        is_using_default=custom_prompt is None,
    )


@router.put("/agents/{agent_name}/prompt", response_model=AgentPromptResponse)
async def update_agent_prompt(
    tenant_id: UUID,
    agent_name: str,
    body: AgentPromptUpdate,
    service: AdminService = Depends(get_admin_service),
    user: CurrentUser = Depends(get_current_user),
) -> AgentPromptResponse:
    """Update the prompt for an agent.

    DEPRECATED: Los prompts ahora viven en archivos de configuración.
    Para modificar un prompt:
    1. Editar docs/prompts/{agent}-agent.md
    2. Commit + push
    3. Railway redeploya automáticamente
    
    Este endpoint se mantiene por compatibilidad pero no tiene efecto.
    """
    raise HTTPException(
        status_code=400,
        detail={
            "error": "Los prompts son de solo lectura",
            "message": "Para modificar un prompt, editá docs/prompts/{agent}-agent.md y pusheá a git",
            "docs": "https://github.com/pablodma/homeAssistant-asistant/tree/main/docs/prompts",
        },
    )


@router.get("/agents/{agent_name}/prompt/history", response_model=list[AgentPromptHistory])
async def get_prompt_history(
    tenant_id: UUID,
    agent_name: str,
    limit: int = Query(10, ge=1, le=50),
    service: AdminService = Depends(get_admin_service),
    _: CurrentUser = Depends(get_current_user),
) -> list[AgentPromptHistory]:
    """Get version history for an agent's prompt.

    Returns the last N versions of the prompt with metadata.
    """
    history = await service.get_prompt_history(str(tenant_id), agent_name, limit)
    return [AgentPromptHistory(**h) for h in history]


# =====================================================
# INTERACTIONS
# =====================================================


@router.get("/interactions", response_model=InteractionListResponse)
async def list_interactions(
    tenant_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_phone: Optional[str] = None,
    agent_used: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    search: Optional[str] = None,
    service: AdminService = Depends(get_admin_service),
    _: CurrentUser = Depends(get_current_user),
) -> InteractionListResponse:
    """List bot interactions with filtering and pagination.

    Supports filtering by user phone, agent, date range, and text search.
    Returns paginated results with total count.
    """
    return await service.get_interactions(
        tenant_id=str(tenant_id),
        page=page,
        page_size=page_size,
        user_phone=user_phone,
        agent_used=agent_used,
        start_date=start_date,
        end_date=end_date,
        search=search,
    )


@router.get("/interactions/{interaction_id}", response_model=InteractionResponse)
async def get_interaction(
    tenant_id: UUID,
    interaction_id: UUID,
    service: AdminService = Depends(get_admin_service),
    _: CurrentUser = Depends(get_current_user),
) -> InteractionResponse:
    """Get details of a specific interaction.

    Returns full details including message content, tokens used,
    response time, and metadata.
    """
    interaction = await service.get_interaction(str(tenant_id), str(interaction_id))
    if not interaction:
        raise HTTPException(status_code=404, detail="Interaction not found")
    return interaction


# =====================================================
# STATISTICS
# =====================================================


@router.get("/stats", response_model=StatsResponse)
async def get_stats(
    tenant_id: UUID,
    days: int = Query(30, ge=1, le=365),
    service: AdminService = Depends(get_admin_service),
    _: CurrentUser = Depends(get_current_user),
) -> StatsResponse:
    """Get statistics for the admin dashboard.

    Returns aggregated statistics including:
    - Total messages and users
    - Token usage
    - Average response time
    - Breakdown by agent
    - Daily activity
    """
    return await service.get_stats(str(tenant_id), days)


# =====================================================
# QUALITY ISSUES
# =====================================================


@router.get("/quality-issues", response_model=QualityIssueListResponse)
async def list_quality_issues(
    tenant_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    issue_type: Optional[str] = Query(None, pattern="^(hard_error|soft_error)$"),
    issue_category: Optional[str] = None,
    severity: Optional[str] = Query(None, pattern="^(low|medium|high|critical)$"),
    agent_name: Optional[str] = None,
    is_resolved: Optional[bool] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    service: AdminService = Depends(get_admin_service),
    _: CurrentUser = Depends(get_current_user),
) -> QualityIssueListResponse:
    """List quality issues with filtering and pagination.

    Supports filtering by:
    - issue_type: 'hard_error' or 'soft_error'
    - issue_category: specific error category
    - severity: 'low', 'medium', 'high', 'critical'
    - agent_name: filter by agent
    - is_resolved: true/false
    - date range
    """
    return await service.get_quality_issues(
        tenant_id=str(tenant_id),
        page=page,
        page_size=page_size,
        issue_type=issue_type,
        issue_category=issue_category,
        severity=severity,
        agent_name=agent_name,
        is_resolved=is_resolved,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/quality-issues/counts", response_model=QualityIssueCounts)
async def get_quality_issue_counts(
    tenant_id: UUID,
    days: int = Query(30, ge=1, le=365),
    service: AdminService = Depends(get_admin_service),
    _: CurrentUser = Depends(get_current_user),
) -> QualityIssueCounts:
    """Get counts of quality issues for summary cards.

    Returns aggregated counts by type, category, and severity.
    """
    return await service.get_quality_issue_counts(str(tenant_id), days)


@router.get("/quality-issues/{issue_id}", response_model=QualityIssueResponse)
async def get_quality_issue(
    tenant_id: UUID,
    issue_id: UUID,
    service: AdminService = Depends(get_admin_service),
    _: CurrentUser = Depends(get_current_user),
) -> QualityIssueResponse:
    """Get details of a specific quality issue.

    Returns full details including error message, stack trace (for hard errors),
    and QA analysis (for soft errors).
    """
    issue = await service.get_quality_issue(str(tenant_id), str(issue_id))
    if not issue:
        raise HTTPException(status_code=404, detail="Quality issue not found")
    return issue


@router.patch("/quality-issues/{issue_id}/resolve", response_model=QualityIssueResponse)
async def resolve_quality_issue(
    tenant_id: UUID,
    issue_id: UUID,
    body: QualityIssueResolve,
    service: AdminService = Depends(get_admin_service),
    user: CurrentUser = Depends(get_current_user),
) -> QualityIssueResponse:
    """Mark a quality issue as resolved.

    Optionally include resolution notes explaining how the issue was fixed.
    """
    issue = await service.resolve_quality_issue(
        tenant_id=str(tenant_id),
        issue_id=str(issue_id),
        resolved_by=body.resolved_by or user.email,
        resolution_notes=body.resolution_notes,
    )
    if not issue:
        raise HTTPException(status_code=404, detail="Quality issue not found")
    return issue
