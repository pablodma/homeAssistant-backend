"""Reminders repository for direct database access."""

from datetime import datetime
from typing import Any
from uuid import UUID

import asyncpg

from ..config.database import fetch_all, fetch_one, get_connection


async def create_reminder(
    tenant_id: UUID,
    user_id: UUID,
    message: str,
    trigger_at: datetime,
    recurrence_rule: str | None = None,
) -> asyncpg.Record:
    """Create a new reminder."""
    query = """
        INSERT INTO reminders (tenant_id, user_id, message, trigger_at, recurrence_rule)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING *
    """
    return await fetch_one(query, tenant_id, user_id, message, trigger_at, recurrence_rule)


async def get_pending_reminders(
    tenant_id: UUID,
    user_id: UUID,
    search: str | None = None,
    limit: int = 20,
) -> list[asyncpg.Record]:
    """Get pending reminders for a user."""
    conditions = [
        "tenant_id = $1",
        "user_id = $2",
        "(trigger_at >= NOW() OR recurrence_rule IS NOT NULL)",
        "status = 'pending'",
    ]
    params: list[Any] = [tenant_id, user_id]
    param_idx = 3

    if search:
        conditions.append(f"message ILIKE ${param_idx}")
        params.append(f"%{search}%")
        param_idx += 1

    where_clause = " AND ".join(conditions)
    query = f"""
        SELECT id, message, trigger_at, recurrence_rule, status, created_at
        FROM reminders
        WHERE {where_clause}
        ORDER BY trigger_at ASC
        LIMIT ${param_idx}
    """
    params.append(limit)
    return await fetch_all(query, *params)


async def delete_reminder_by_search(
    tenant_id: UUID,
    user_id: UUID,
    search_query: str,
) -> asyncpg.Record | None:
    """Soft-delete a reminder by search text (sets status to 'cancelled')."""
    query = """
        UPDATE reminders SET status = 'cancelled'
        WHERE tenant_id = $1 AND user_id = $2
          AND message ILIKE $3 AND status = 'pending'
        RETURNING id, message
    """
    return await fetch_one(query, tenant_id, user_id, f"%{search_query}%")


async def update_reminder_by_search(
    tenant_id: UUID,
    user_id: UUID,
    search_query: str,
    message: str | None = None,
    trigger_at: datetime | None = None,
    recurrence_rule: str | None = None,
) -> asyncpg.Record | None:
    """Find a pending reminder by search text and update it."""
    find_query = """
        SELECT id FROM reminders
        WHERE tenant_id = $1 AND user_id = $2
          AND message ILIKE $3 AND status = 'pending'
        LIMIT 1
    """
    row = await fetch_one(find_query, tenant_id, user_id, f"%{search_query}%")
    if not row:
        return None

    updates = ["updated_at = NOW()"]
    params: list[Any] = [tenant_id, row["id"]]
    param_idx = 3

    if message is not None:
        updates.append(f"message = ${param_idx}")
        params.append(message)
        param_idx += 1
    if trigger_at is not None:
        updates.append(f"trigger_at = ${param_idx}")
        params.append(trigger_at)
        param_idx += 1
    if recurrence_rule is not None:
        rec_val = None if recurrence_rule == "none" else recurrence_rule
        updates.append(f"recurrence_rule = ${param_idx}")
        params.append(rec_val)
        param_idx += 1

    if len(updates) == 1:  # only updated_at
        return row

    update_query = f"""
        UPDATE reminders SET {', '.join(updates)}
        WHERE tenant_id = $1 AND id = $2
        RETURNING id, message, trigger_at, recurrence_rule
    """
    return await fetch_one(update_query, *params)


async def complete_reminder_by_search(
    tenant_id: UUID,
    user_id: UUID,
    search_query: str,
) -> asyncpg.Record | None:
    """Mark a pending reminder as completed by search text."""
    query = """
        UPDATE reminders SET status = 'completed'
        WHERE tenant_id = $1 AND user_id = $2
          AND message ILIKE $3 AND status = 'pending'
        RETURNING id, message
    """
    return await fetch_one(query, tenant_id, user_id, f"%{search_query}%")


async def get_user_by_phone(phone: str) -> asyncpg.Record | None:
    """Get user by phone number with Argentina mobile normalization."""
    normalized = phone.strip()
    if not normalized.startswith("+"):
        normalized = f"+{normalized}"

    if normalized.startswith("+54") and not normalized.startswith("+549"):
        rest = normalized[3:]
        if len(rest) == 10:
            normalized = f"+549{rest}"

    phone_variants = [normalized]
    if normalized.startswith("+549"):
        phone_variants.append(f"+54{normalized[4:]}")

    query = """
        SELECT id, tenant_id, phone, email, display_name, role
        FROM users
        WHERE phone = ANY($1)
          AND is_active = true
    """
    return await fetch_one(query, phone_variants)
