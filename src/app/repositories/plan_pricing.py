"""Plan pricing repository for database operations."""

import json
from decimal import Decimal
from typing import Any
from uuid import UUID

from ..config.database import get_pool


def _parse_plan_row(row: dict[str, Any]) -> dict[str, Any]:
    """Parse plan row, converting JSONB fields."""
    if row and "features" in row:
        features = row["features"]
        if isinstance(features, str):
            row["features"] = json.loads(features)
    return row


# =============================================================================
# Plan Pricing Operations
# =============================================================================

async def get_all_plans(active_only: bool = True) -> list[dict[str, Any]]:
    """Get all plans."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        if active_only:
            rows = await conn.fetch(
                """
                SELECT * FROM plan_pricing 
                WHERE active = true
                ORDER BY price_monthly ASC
                """
            )
        else:
            rows = await conn.fetch(
                """
                SELECT * FROM plan_pricing 
                ORDER BY price_monthly ASC
                """
            )
        return [_parse_plan_row(dict(row)) for row in rows]


async def get_plan_by_type(plan_type: str) -> dict[str, Any] | None:
    """Get plan by type (starter, family, premium)."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM plan_pricing WHERE plan_type = $1",
            plan_type
        )
        return _parse_plan_row(dict(row)) if row else None


async def get_plan_by_id(plan_id: UUID) -> dict[str, Any] | None:
    """Get plan by ID."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM plan_pricing WHERE id = $1",
            plan_id
        )
        return _parse_plan_row(dict(row)) if row else None


async def update_plan_pricing(
    plan_type: str,
    updated_by: UUID,
    name: str | None = None,
    description: str | None = None,
    price_monthly: Decimal | None = None,
    currency: str | None = None,
    max_members: int | None = None,
    max_messages_month: int | None = None,
    history_days: int | None = None,
    features: list[str] | None = None,
) -> dict[str, Any] | None:
    """
    Update plan pricing.
    
    Note: Cannot update starter plan price (always 0).
    """
    pool = await get_pool()

    # Build dynamic update query
    fields = ["updated_at = NOW()", "updated_by = $1"]
    values: list[Any] = [updated_by]
    idx = 2

    if name is not None:
        fields.append(f"name = ${idx}")
        values.append(name)
        idx += 1

    if description is not None:
        fields.append(f"description = ${idx}")
        values.append(description)
        idx += 1

    # Only allow price update for non-starter plans
    if price_monthly is not None and plan_type != "starter":
        fields.append(f"price_monthly = ${idx}")
        values.append(price_monthly)
        idx += 1

    if currency is not None:
        fields.append(f"currency = ${idx}")
        values.append(currency)
        idx += 1

    if max_members is not None:
        fields.append(f"max_members = ${idx}")
        values.append(max_members)
        idx += 1

    if max_messages_month is not None:
        fields.append(f"max_messages_month = ${idx}")
        values.append(max_messages_month if max_messages_month > 0 else None)
        idx += 1

    if history_days is not None:
        fields.append(f"history_days = ${idx}")
        values.append(history_days)
        idx += 1

    if features is not None:
        fields.append(f"features = ${idx}")
        values.append(features)
        idx += 1

    values.append(plan_type)
    query = f"""
        UPDATE plan_pricing 
        SET {', '.join(fields)}
        WHERE plan_type = ${idx}
        RETURNING *
    """

    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, *values)
        return _parse_plan_row(dict(row)) if row else None


async def get_plan_price(plan_type: str) -> Decimal | None:
    """Get just the price for a plan."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        price = await conn.fetchval(
            "SELECT price_monthly FROM plan_pricing WHERE plan_type = $1",
            plan_type
        )
        return price


async def get_plan_limits(plan_type: str) -> dict[str, Any] | None:
    """Get limits for a plan (members, messages, history)."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT max_members, max_messages_month, history_days 
            FROM plan_pricing 
            WHERE plan_type = $1
            """,
            plan_type
        )
        return dict(row) if row else None


async def compare_plans(
    current_plan_type: str,
    target_plan_type: str,
) -> dict[str, Any] | None:
    """Compare two plans and return differences."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM plan_pricing 
            WHERE plan_type IN ($1, $2)
            """,
            current_plan_type, target_plan_type
        )
        
        if len(rows) != 2:
            return None

        plans = {row["plan_type"]: _parse_plan_row(dict(row)) for row in rows}
        current = plans.get(current_plan_type)
        target = plans.get(target_plan_type)

        if not current or not target:
            return None

        return {
            "current_plan": current,
            "target_plan": target,
            "price_difference": target["price_monthly"] - current["price_monthly"],
            "is_upgrade": target["price_monthly"] > current["price_monthly"],
        }
