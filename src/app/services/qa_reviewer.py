"""QA Review History & Rollback - Database-only operations.

The actual QA review analysis and prompt improvement logic has been
moved to homeai-assis (triggered via POST /internal/qa-review).

This module only provides:
- get_review_history(): Read past review cycles from DB
- rollback_revision(): Restore a prompt to its pre-review state via GitHub
"""

import json
from typing import Any

import structlog

from ..config.database import get_pool
from .github import GitHubService, GitHubServiceError

logger = structlog.get_logger()


class QAReviewService:
    """Service for reading QA review history and performing rollbacks.

    No LLM dependency - all AI logic lives in homeai-assis.
    """

    def __init__(self):
        self.github = GitHubService()

    async def get_review_history(
        self,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Get history of QA review cycles.

        Args:
            limit: Maximum number of cycles to return.

        Returns:
            List of review cycle summaries.
        """
        pool = await get_pool()

        rows = await pool.fetch(
            """
            SELECT
                c.id, c.triggered_by, c.period_start, c.period_end,
                c.issues_analyzed_count, c.improvements_applied_count,
                c.status, c.error_message, c.created_at, c.completed_at,
                c.analysis_result,
                COALESCE(
                    json_agg(
                        json_build_object(
                            'id', r.id,
                            'agent_name', r.agent_name,
                            'improvement_reason', r.improvement_reason,
                            'github_commit_url', r.github_commit_url,
                            'is_rolled_back', r.is_rolled_back,
                            'created_at', r.created_at
                        )
                    ) FILTER (WHERE r.id IS NOT NULL),
                    '[]'::json
                ) as revisions
            FROM qa_review_cycles c
            LEFT JOIN prompt_revisions r ON r.review_cycle_id = c.id
            GROUP BY c.id
            ORDER BY c.created_at DESC
            LIMIT $1
            """,
            limit,
        )

        return [dict(row) for row in rows]

    async def rollback_revision(
        self,
        revision_id: str,
        rolled_back_by: str,
    ) -> dict[str, Any]:
        """Rollback a prompt revision by restoring the original prompt.

        Args:
            revision_id: The revision to rollback.
            rolled_back_by: Email of the admin performing the rollback.

        Returns:
            Rollback result with commit info.
        """
        pool = await get_pool()

        # Get the revision
        revision = await pool.fetchrow(
            """
            SELECT id, agent_name, original_prompt, is_rolled_back
            FROM prompt_revisions
            WHERE id = $1
            """,
            revision_id,
        )

        if not revision:
            raise ValueError(f"Revision {revision_id} not found")

        if revision["is_rolled_back"]:
            raise ValueError(f"Revision {revision_id} is already rolled back")

        agent_name = revision["agent_name"]
        original_prompt = revision["original_prompt"]

        # Restore original prompt via GitHub
        try:
            result = await self.github.update_prompt(
                agent_name=agent_name,
                content=original_prompt,
                updated_by=f"rollback by {rolled_back_by}",
            )
        except GitHubServiceError as e:
            raise ValueError(f"Failed to rollback via GitHub: {e.message}")

        # Mark as rolled back
        await pool.execute(
            """
            UPDATE prompt_revisions
            SET is_rolled_back = true, rolled_back_at = NOW(), rolled_back_by = $1,
                rollback_commit_sha = $2, rollback_commit_url = $3
            WHERE id = $4
            """,
            rolled_back_by,
            result["commit_sha"],
            result["commit_url"],
            revision_id,
        )

        logger.info(
            "Prompt revision rolled back",
            revision_id=revision_id,
            agent_name=agent_name,
            commit_sha=result["commit_sha"][:7],
        )

        return {
            "revision_id": revision_id,
            "agent_name": agent_name,
            "commit_sha": result["commit_sha"],
            "commit_url": result["commit_url"],
        }
