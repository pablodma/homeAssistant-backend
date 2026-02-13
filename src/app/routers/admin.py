"""Admin router for agent management."""

import traceback
from datetime import datetime
from typing import Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query

logger = structlog.get_logger()

from ..middleware.auth import get_current_user
from ..schemas.admin import (
    AgentInfo,
    AgentPromptHistory,
    AgentPromptResponse,
    AgentPromptUpdate,
    AgentPromptWithDefault,
    InteractionListResponse,
    InteractionResponse,
    PromptRevisionItem,
    PromptUpdateResponse,
    QAReviewHistoryItem,
    QualityIssueCounts,
    QualityIssueListResponse,
    QualityIssueResolve,
    QualityIssueResponse,
    RollbackResponse,
    StatsResponse,
    get_default_prompt,
)
from ..schemas.auth import CurrentUser
from ..services.admin import AdminService
from ..services.github import GitHubService, GitHubServiceError
from ..services.qa_reviewer import QAReviewService

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
    _: CurrentUser = Depends(get_current_user),
) -> AgentPromptWithDefault:
    """Get the active prompt for an agent.

    Reads from GitHub API (repo homeai-assis). Single source of truth.
    Falls back to local files when GitHub is not configured (dev).
    """
    github = GitHubService()

    if github.is_configured:
        try:
            prompt_content = await github.get_prompt(agent_name)
            return AgentPromptWithDefault(
                agent_name=agent_name,
                custom_prompt=None,
                default_prompt=prompt_content,
                is_using_default=True,
            )
        except GitHubServiceError as e:
            raise HTTPException(
                status_code=e.status_code or 500,
                detail={"error": "Failed to get prompt", "message": e.message},
            )

    # Fallback for local dev when GITHUB_TOKEN not set
    prompt_content = get_default_prompt(agent_name)
    return AgentPromptWithDefault(
        agent_name=agent_name,
        custom_prompt=None,
        default_prompt=prompt_content,
        is_using_default=True,
    )


@router.put("/agents/{agent_name}/prompt", response_model=PromptUpdateResponse)
async def update_agent_prompt(
    tenant_id: UUID,
    agent_name: str,
    body: AgentPromptUpdate,
    user: CurrentUser = Depends(get_current_user),
) -> PromptUpdateResponse:
    """Update the prompt for an agent via GitHub API.

    This endpoint commits the new prompt to the GitHub repository,
    which triggers an automatic Railway deployment (~30 seconds).

    Requires GITHUB_TOKEN environment variable to be configured.
    """
    github = GitHubService()

    if not github.is_configured:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "GitHub integration not configured",
                "message": "Contact the administrator to configure GITHUB_TOKEN",
            },
        )

    try:
        result = await github.update_prompt(
            agent_name=agent_name,
            content=body.prompt_content,
            updated_by=user.email or "admin",
        )

        return PromptUpdateResponse(
            agent_name=agent_name,
            commit_sha=result["commit_sha"],
            commit_url=result["commit_url"],
            file_url=result["file_url"],
        )

    except GitHubServiceError as e:
        raise HTTPException(
            status_code=e.status_code or 500,
            detail={
                "error": "Failed to update prompt",
                "message": e.message,
            },
        )


@router.get("/agents/{agent_name}/prompt/history", response_model=list[AgentPromptHistory])
async def get_prompt_history(
    tenant_id: UUID,
    agent_name: str,
    limit: int = Query(10, ge=1, le=50),
    _: CurrentUser = Depends(get_current_user),
) -> list[AgentPromptHistory]:
    """Get version history for an agent's prompt.

    DEPRECATED: Tabla agent_prompts deprecada. Historial disponible en GitHub.
    Returns empty list. Use GitHub commit history for version tracking.
    """
    return []


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


# =====================================================
# QA REVIEW (History & Rollback only - AI logic in homeai-assis)
# =====================================================


@router.get("/qa-review/history", response_model=list[QAReviewHistoryItem])
async def get_qa_review_history(
    tenant_id: UUID,
    limit: int = Query(20, ge=1, le=100),
    user: CurrentUser = Depends(get_current_user),
) -> list[QAReviewHistoryItem]:
    """Get history of QA review cycles.

    Returns past review executions with their results and applied revisions.
    """
    service = QAReviewService()

    try:
        history = await service.get_review_history(
            tenant_id=str(tenant_id),
            limit=limit,
        )
        return [QAReviewHistoryItem(**item) for item in history]

    except Exception as e:
        logger.error("QA review history failed", error=str(e), traceback=traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail={"error": "Failed to get review history", "message": str(e)},
        )


@router.post("/qa-review/rollback/{revision_id}", response_model=RollbackResponse)
async def rollback_prompt_revision(
    tenant_id: UUID,
    revision_id: UUID,
    user: CurrentUser = Depends(get_current_user),
) -> RollbackResponse:
    """Rollback a prompt revision.

    Restores the original prompt content before the QA review modification.
    Creates a new GitHub commit with the restored content.
    """
    service = QAReviewService()

    try:
        result = await service.rollback_revision(
            tenant_id=str(tenant_id),
            revision_id=str(revision_id),
            rolled_back_by=user.email or "admin",
        )
        return RollbackResponse(**result)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Rollback endpoint failed", error=str(e), traceback=traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail={"error": "Rollback failed", "message": str(e)},
        )
