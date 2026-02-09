"""Admin service for agent management."""

from datetime import datetime
from typing import Any, Optional

import structlog

from ..repositories.admin import AdminRepository
from ..schemas.admin import (
    AGENT_DEFINITIONS,
    AgentInfo,
    AgentPromptResponse,
    InteractionListResponse,
    InteractionResponse,
    QualityIssueCounts,
    QualityIssueListResponse,
    QualityIssueResponse,
    StatsResponse,
)

logger = structlog.get_logger()


class AdminService:
    """Service for admin operations."""

    def __init__(self):
        self.repo = AdminRepository()

    # =====================================================
    # AGENTS
    # =====================================================

    async def get_agents(self, tenant_id: str) -> list[AgentInfo]:
        """Get list of all agents with their status."""
        # Get prompts from database
        prompts = await self.repo.get_prompts(tenant_id)
        prompt_map = {p["agent_name"]: p for p in prompts}

        # Merge with definitions
        agents = []
        for agent_def in AGENT_DEFINITIONS:
            agent = AgentInfo(
                name=agent_def.name,
                display_name=agent_def.display_name,
                description=agent_def.description,
                has_prompt=agent_def.name in prompt_map,
                is_active=True,
                last_updated=prompt_map.get(agent_def.name, {}).get("updated_at"),
            )
            agents.append(agent)

        return agents

    # =====================================================
    # PROMPTS
    # =====================================================

    async def get_prompt(
        self, tenant_id: str, agent_name: str
    ) -> Optional[AgentPromptResponse]:
        """Get the active prompt for an agent."""
        data = await self.repo.get_prompt(tenant_id, agent_name)
        if data:
            return AgentPromptResponse(**data)
        return None

    async def update_prompt(
        self,
        tenant_id: str,
        agent_name: str,
        prompt_content: str,
        created_by: Optional[str] = None,
    ) -> AgentPromptResponse:
        """Update (create new version of) a prompt."""
        data = await self.repo.create_prompt(
            tenant_id=tenant_id,
            agent_name=agent_name,
            prompt_content=prompt_content,
            created_by=created_by,
        )
        return AgentPromptResponse(**data)

    async def get_prompt_history(
        self, tenant_id: str, agent_name: str, limit: int = 10
    ) -> list[dict[str, Any]]:
        """Get version history for a prompt."""
        return await self.repo.get_prompt_history(tenant_id, agent_name, limit)

    # =====================================================
    # INTERACTIONS
    # =====================================================

    async def get_interactions(
        self,
        tenant_id: str,
        page: int = 1,
        page_size: int = 20,
        user_phone: Optional[str] = None,
        agent_used: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        search: Optional[str] = None,
    ) -> InteractionListResponse:
        """Get paginated list of interactions."""
        items, total = await self.repo.get_interactions(
            tenant_id=tenant_id,
            page=page,
            page_size=page_size,
            user_phone=user_phone,
            agent_used=agent_used,
            start_date=start_date,
            end_date=end_date,
            search=search,
        )

        total_pages = (total + page_size - 1) // page_size

        return InteractionListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    async def get_interaction(
        self, tenant_id: str, interaction_id: str
    ) -> Optional[InteractionResponse]:
        """Get a single interaction by ID."""
        data = await self.repo.get_interaction(tenant_id, interaction_id)
        if data:
            return InteractionResponse(**data)
        return None

    # =====================================================
    # STATISTICS
    # =====================================================

    async def get_stats(
        self, tenant_id: str, days: int = 30
    ) -> StatsResponse:
        """Get statistics for the admin dashboard."""
        data = await self.repo.get_stats(tenant_id, days)
        return StatsResponse(**data)

    # =====================================================
    # QUALITY ISSUES
    # =====================================================

    async def get_quality_issues(
        self,
        tenant_id: str,
        page: int = 1,
        page_size: int = 50,
        issue_type: Optional[str] = None,
        issue_category: Optional[str] = None,
        severity: Optional[str] = None,
        agent_name: Optional[str] = None,
        is_resolved: Optional[bool] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> QualityIssueListResponse:
        """Get paginated list of quality issues."""
        items, total = await self.repo.get_quality_issues(
            tenant_id=tenant_id,
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

        total_pages = (total + page_size - 1) // page_size

        return QualityIssueListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    async def get_quality_issue(
        self, tenant_id: str, issue_id: str
    ) -> Optional[QualityIssueResponse]:
        """Get a single quality issue by ID."""
        data = await self.repo.get_quality_issue(tenant_id, issue_id)
        if data:
            return QualityIssueResponse(**data)
        return None

    async def resolve_quality_issue(
        self,
        tenant_id: str,
        issue_id: str,
        resolved_by: Optional[str] = None,
        resolution_notes: Optional[str] = None,
    ) -> Optional[QualityIssueResponse]:
        """Mark a quality issue as resolved."""
        data = await self.repo.resolve_quality_issue(
            tenant_id=tenant_id,
            issue_id=issue_id,
            resolved_by=resolved_by,
            resolution_notes=resolution_notes,
        )
        if data:
            return QualityIssueResponse(**data)
        return None

    async def get_quality_issue_counts(
        self, tenant_id: str, days: int = 30
    ) -> QualityIssueCounts:
        """Get counts of quality issues."""
        data = await self.repo.get_quality_issue_counts(tenant_id, days)
        return QualityIssueCounts(**data)
