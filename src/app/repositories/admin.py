"""Admin repository for platform management.

All admin queries are global (no tenant scoping).
The admin panel is a platform management tool that views data across all tenants.
"""

from datetime import datetime, timedelta
from typing import Any, Optional

import structlog

from ..config.database import get_pool

logger = structlog.get_logger()


class AdminRepository:
    """Repository for admin operations."""

    # =====================================================
    # AGENT PROMPTS
    # =====================================================

    async def get_prompts(self) -> list[dict[str, Any]]:
        """Get all active prompts."""
        pool = await get_pool()
        query = """
            SELECT id, tenant_id, agent_name, prompt_content, version, is_active, 
                   created_at, updated_at
            FROM agent_prompts
            WHERE is_active = true
            ORDER BY agent_name
        """
        rows = await pool.fetch(query)
        return [dict(row) for row in rows]

    async def get_prompt(
        self, agent_name: str
    ) -> Optional[dict[str, Any]]:
        """Get active prompt for an agent."""
        pool = await get_pool()
        query = """
            SELECT id, tenant_id, agent_name, prompt_content, version, is_active,
                   created_at, updated_at
            FROM agent_prompts
            WHERE agent_name = $1 AND is_active = true
        """
        row = await pool.fetchrow(query, agent_name)
        return dict(row) if row else None

    async def create_prompt(
        self,
        agent_name: str,
        prompt_content: str,
        created_by: Optional[str] = None,
    ) -> dict[str, Any]:
        """Create a new prompt (deactivates previous version)."""
        pool = await get_pool()

        async with pool.acquire() as conn:
            async with conn.transaction():
                # Deactivate previous version
                await conn.execute(
                    """
                    UPDATE agent_prompts 
                    SET is_active = false, updated_at = NOW()
                    WHERE agent_name = $1 AND is_active = true
                    """,
                    agent_name,
                )

                # Get next version number
                version_row = await conn.fetchrow(
                    """
                    SELECT COALESCE(MAX(version), 0) + 1 as next_version
                    FROM agent_prompts
                    WHERE agent_name = $1
                    """,
                    agent_name,
                )
                next_version = version_row["next_version"]

                # Insert new prompt
                row = await conn.fetchrow(
                    """
                    INSERT INTO agent_prompts (
                        agent_name, prompt_content, version, is_active, created_by
                    ) VALUES ($1, $2, $3, true, $4)
                    RETURNING id, tenant_id, agent_name, prompt_content, version, is_active,
                              created_at, updated_at
                    """,
                    agent_name,
                    prompt_content,
                    next_version,
                    created_by,
                )

                return dict(row)

    async def get_prompt_history(
        self, agent_name: str, limit: int = 10
    ) -> list[dict[str, Any]]:
        """Get version history for a prompt."""
        pool = await get_pool()
        query = """
            SELECT id, version, is_active, created_at,
                   LEFT(prompt_content, 200) as prompt_preview
            FROM agent_prompts
            WHERE agent_name = $1
            ORDER BY version DESC
            LIMIT $2
        """
        rows = await pool.fetch(query, agent_name, limit)
        return [dict(row) for row in rows]

    # =====================================================
    # AGENT INTERACTIONS
    # =====================================================

    async def get_interactions(
        self,
        page: int = 1,
        page_size: int = 20,
        user_phone: Optional[str] = None,
        agent_used: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        search: Optional[str] = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """Get paginated interactions with filters."""
        pool = await get_pool()

        conditions: list[str] = []
        params: list[Any] = []
        param_idx = 1

        if user_phone:
            conditions.append(f"user_phone = ${param_idx}")
            params.append(user_phone)
            param_idx += 1

        if agent_used:
            conditions.append(f"agent_used = ${param_idx}")
            params.append(agent_used)
            param_idx += 1

        if start_date:
            conditions.append(f"created_at >= ${param_idx}")
            params.append(start_date)
            param_idx += 1

        if end_date:
            conditions.append(f"created_at <= ${param_idx}")
            params.append(end_date)
            param_idx += 1

        if search:
            conditions.append(f"(message_in ILIKE ${param_idx} OR message_out ILIKE ${param_idx})")
            params.append(f"%{search}%")
            param_idx += 1

        where_clause = " AND ".join(conditions) if conditions else "TRUE"

        # Count total
        count_query = f"SELECT COUNT(*) FROM agent_interactions WHERE {where_clause}"
        count_row = await pool.fetchrow(count_query, *params)
        total = count_row["count"]

        # Get page
        offset = (page - 1) * page_size
        query = f"""
            SELECT id, user_phone, user_name,
                   LEFT(message_in, 100) as message_preview,
                   agent_used, sub_agent_used, response_time_ms, created_at
            FROM agent_interactions
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """
        params.extend([page_size, offset])

        rows = await pool.fetch(query, *params)
        return [dict(row) for row in rows], total

    async def get_interaction(
        self, interaction_id: str
    ) -> Optional[dict[str, Any]]:
        """Get a single interaction by ID."""
        pool = await get_pool()
        query = """
            SELECT id, tenant_id, user_phone, user_name, message_in, message_out,
                   agent_used, sub_agent_used, tokens_in, tokens_out,
                   response_time_ms, created_at, metadata
            FROM agent_interactions
            WHERE id = $1
        """
        row = await pool.fetchrow(query, interaction_id)
        return dict(row) if row else None

    # =====================================================
    # STATISTICS
    # =====================================================

    async def get_stats(
        self,
        days: int = 30,
    ) -> dict[str, Any]:
        """Get statistics for the admin dashboard."""
        pool = await get_pool()
        start_date = datetime.now() - timedelta(days=days)

        # Overall stats
        overall_query = """
            SELECT 
                COUNT(*) as total_messages,
                COUNT(DISTINCT user_phone) as total_users,
                COALESCE(SUM(tokens_in + tokens_out), 0) as total_tokens,
                AVG(response_time_ms) as avg_response_time_ms
            FROM agent_interactions
            WHERE created_at >= $1
        """
        overall = await pool.fetchrow(overall_query, start_date)

        # By agent
        by_agent_query = """
            SELECT 
                agent_used as agent_name,
                COUNT(*) as total_messages,
                AVG(response_time_ms) as avg_response_time_ms,
                COALESCE(SUM(tokens_in + tokens_out), 0) as total_tokens
            FROM agent_interactions
            WHERE created_at >= $1
            GROUP BY agent_used
            ORDER BY total_messages DESC
        """
        by_agent_rows = await pool.fetch(by_agent_query, start_date)

        # By day
        by_day_query = """
            SELECT 
                DATE(created_at) as date,
                COUNT(*) as message_count,
                COUNT(DISTINCT user_phone) as unique_users,
                COALESCE(SUM(tokens_in + tokens_out), 0) as total_tokens
            FROM agent_interactions
            WHERE created_at >= $1
            GROUP BY DATE(created_at)
            ORDER BY date DESC
            LIMIT 30
        """
        by_day_rows = await pool.fetch(by_day_query, start_date)

        return {
            "total_messages": overall["total_messages"],
            "total_users": overall["total_users"],
            "total_tokens": overall["total_tokens"],
            "avg_response_time_ms": overall["avg_response_time_ms"],
            "by_agent": [dict(row) for row in by_agent_rows],
            "by_day": [
                {
                    "date": row["date"].strftime("%Y-%m-%d"),
                    "message_count": row["message_count"],
                    "unique_users": row["unique_users"],
                    "total_tokens": row["total_tokens"],
                }
                for row in by_day_rows
            ],
        }

    # =====================================================
    # QUALITY ISSUES
    # =====================================================

    async def get_quality_issues(
        self,
        page: int = 1,
        page_size: int = 50,
        issue_type: Optional[str] = None,
        issue_category: Optional[str] = None,
        severity: Optional[str] = None,
        agent_name: Optional[str] = None,
        is_resolved: Optional[bool] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """Get paginated quality issues with filters."""
        pool = await get_pool()

        conditions: list[str] = []
        params: list[Any] = []
        param_idx = 1

        if issue_type:
            conditions.append(f"issue_type = ${param_idx}")
            params.append(issue_type)
            param_idx += 1

        if issue_category:
            conditions.append(f"issue_category = ${param_idx}")
            params.append(issue_category)
            param_idx += 1

        if severity:
            conditions.append(f"severity = ${param_idx}")
            params.append(severity)
            param_idx += 1

        if agent_name:
            conditions.append(f"agent_name = ${param_idx}")
            params.append(agent_name)
            param_idx += 1

        if is_resolved is not None:
            conditions.append(f"is_resolved = ${param_idx}")
            params.append(is_resolved)
            param_idx += 1

        if start_date:
            conditions.append(f"created_at >= ${param_idx}")
            params.append(start_date)
            param_idx += 1

        if end_date:
            conditions.append(f"created_at <= ${param_idx}")
            params.append(end_date)
            param_idx += 1

        where_clause = " AND ".join(conditions) if conditions else "TRUE"

        # Count total
        count_query = f"SELECT COUNT(*) FROM quality_issues WHERE {where_clause}"
        count_row = await pool.fetchrow(count_query, *params)
        total = count_row["count"]

        # Get page
        offset = (page - 1) * page_size
        query = f"""
            SELECT id, issue_type, issue_category, severity, agent_name, user_phone,
                   LEFT(message_in, 100) as message_preview,
                   LEFT(error_message, 150) as error_preview,
                   is_resolved, created_at
            FROM quality_issues
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """
        params.extend([page_size, offset])

        rows = await pool.fetch(query, *params)
        return [dict(row) for row in rows], total

    async def get_quality_issue(
        self, issue_id: str
    ) -> Optional[dict[str, Any]]:
        """Get a single quality issue by ID."""
        pool = await get_pool()
        query = """
            SELECT id, tenant_id, interaction_id, issue_type, issue_category,
                   user_phone, agent_name, tool_name, message_in, message_out,
                   error_code, error_message, severity,
                   qa_analysis, qa_suggestion, qa_confidence,
                   request_payload, stack_trace, correlation_id,
                   is_resolved, resolved_at, resolved_by, resolution_notes,
                   admin_insight, fix_status, fix_error, fix_result, created_at
            FROM quality_issues
            WHERE id = $1
        """
        row = await pool.fetchrow(query, issue_id)
        return dict(row) if row else None

    async def update_issue_insight(
        self,
        issue_id: str,
        admin_insight: str,
    ) -> Optional[dict[str, Any]]:
        """Update the admin insight for a quality issue."""
        pool = await get_pool()
        query = """
            UPDATE quality_issues
            SET admin_insight = $2
            WHERE id = $1
            RETURNING id, tenant_id, interaction_id, issue_type, issue_category,
                      user_phone, agent_name, tool_name, message_in, message_out,
                      error_code, error_message, severity,
                      qa_analysis, qa_suggestion, qa_confidence,
                      request_payload, stack_trace, correlation_id,
                      is_resolved, resolved_at, resolved_by, resolution_notes,
                      admin_insight, fix_status, fix_error, fix_result, created_at
        """
        row = await pool.fetchrow(query, issue_id, admin_insight)
        return dict(row) if row else None

    async def resolve_quality_issue(
        self,
        issue_id: str,
        resolved_by: Optional[str] = None,
        resolution_notes: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        """Mark a quality issue as resolved."""
        pool = await get_pool()
        query = """
            UPDATE quality_issues
            SET is_resolved = true,
                resolved_at = NOW(),
                resolved_by = $2,
                resolution_notes = $3
            WHERE id = $1
            RETURNING id, tenant_id, interaction_id, issue_type, issue_category,
                      user_phone, agent_name, tool_name, message_in, message_out,
                      error_code, error_message, severity,
                      qa_analysis, qa_suggestion, qa_confidence,
                      request_payload, stack_trace, correlation_id,
                      is_resolved, resolved_at, resolved_by, resolution_notes,
                      admin_insight, fix_status, fix_error, fix_result, created_at
        """
        row = await pool.fetchrow(query, issue_id, resolved_by, resolution_notes)
        return dict(row) if row else None

    async def get_quality_issue_counts(
        self,
        days: int = 30,
    ) -> dict[str, Any]:
        """Get counts of quality issues for summary."""
        pool = await get_pool()
        start_date = datetime.now() - timedelta(days=days)

        # Overall counts
        counts_query = """
            SELECT 
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE issue_type = 'hard_error') as hard_errors,
                COUNT(*) FILTER (WHERE issue_type = 'soft_error') as soft_errors,
                COUNT(*) FILTER (WHERE is_resolved = false) as unresolved
            FROM quality_issues
            WHERE created_at >= $1
        """
        counts = await pool.fetchrow(counts_query, start_date)

        # By category
        by_category_query = """
            SELECT issue_category, COUNT(*) as count
            FROM quality_issues
            WHERE created_at >= $1
            GROUP BY issue_category
        """
        by_category_rows = await pool.fetch(by_category_query, start_date)

        # By severity
        by_severity_query = """
            SELECT severity, COUNT(*) as count
            FROM quality_issues
            WHERE created_at >= $1
            GROUP BY severity
        """
        by_severity_rows = await pool.fetch(by_severity_query, start_date)

        return {
            "total": counts["total"],
            "hard_errors": counts["hard_errors"],
            "soft_errors": counts["soft_errors"],
            "unresolved": counts["unresolved"],
            "by_category": {row["issue_category"]: row["count"] for row in by_category_rows},
            "by_severity": {row["severity"]: row["count"] for row in by_severity_rows},
        }
