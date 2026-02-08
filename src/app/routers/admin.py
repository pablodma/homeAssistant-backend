"""Admin router for agent management."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from ..middleware.auth import get_current_user, require_auth
from ..schemas.admin import (
    AgentInfo,
    AgentPromptHistory,
    AgentPromptResponse,
    AgentPromptUpdate,
    InteractionListResponse,
    InteractionResponse,
    StatsResponse,
)
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
    _: dict = Depends(require_auth),
) -> list[AgentInfo]:
    """List all available agents with their status.

    Returns information about each agent including whether it has a custom
    prompt configured and when it was last updated.
    """
    return await service.get_agents(str(tenant_id))


# =====================================================
# PROMPTS
# =====================================================


@router.get("/agents/{agent_name}/prompt", response_model=Optional[AgentPromptResponse])
async def get_agent_prompt(
    tenant_id: UUID,
    agent_name: str,
    service: AdminService = Depends(get_admin_service),
    _: dict = Depends(require_auth),
) -> Optional[AgentPromptResponse]:
    """Get the active prompt for an agent.

    Returns the current active prompt content and metadata.
    Returns null if no custom prompt is configured.
    """
    return await service.get_prompt(str(tenant_id), agent_name)


@router.put("/agents/{agent_name}/prompt", response_model=AgentPromptResponse)
async def update_agent_prompt(
    tenant_id: UUID,
    agent_name: str,
    body: AgentPromptUpdate,
    service: AdminService = Depends(get_admin_service),
    user: dict = Depends(require_auth),
) -> AgentPromptResponse:
    """Update the prompt for an agent.

    Creates a new version of the prompt. Previous versions are kept
    for history tracking but marked as inactive.
    """
    return await service.update_prompt(
        tenant_id=str(tenant_id),
        agent_name=agent_name,
        prompt_content=body.prompt_content,
        created_by=user.get("email"),
    )


@router.get("/agents/{agent_name}/prompt/history", response_model=list[AgentPromptHistory])
async def get_prompt_history(
    tenant_id: UUID,
    agent_name: str,
    limit: int = Query(10, ge=1, le=50),
    service: AdminService = Depends(get_admin_service),
    _: dict = Depends(require_auth),
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
    _: dict = Depends(require_auth),
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
    _: dict = Depends(require_auth),
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
    _: dict = Depends(require_auth),
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
