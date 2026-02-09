"""Subscription repository for database operations."""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from ..config.database import get_pool


# =============================================================================
# Subscription Operations
# =============================================================================

async def create_subscription(
    tenant_id: UUID,
    plan_type: str,
    mp_preapproval_id: str | None = None,
    mp_payer_id: str | None = None,
    status: str = "pending",
) -> dict[str, Any]:
    """Create a new subscription."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO subscriptions (
                tenant_id, plan_type, mp_preapproval_id, mp_payer_id, status
            )
            VALUES ($1, $2, $3, $4, $5)
            RETURNING *
            """,
            tenant_id, plan_type, mp_preapproval_id, mp_payer_id, status
        )
        return dict(row)


async def get_subscription_by_id(subscription_id: UUID) -> dict[str, Any] | None:
    """Get subscription by ID."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM subscriptions WHERE id = $1",
            subscription_id
        )
        return dict(row) if row else None


async def get_subscription_by_tenant(tenant_id: UUID) -> dict[str, Any] | None:
    """Get active subscription for a tenant."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT * FROM subscriptions 
            WHERE tenant_id = $1 AND status IN ('pending', 'authorized', 'paused')
            ORDER BY created_at DESC
            LIMIT 1
            """,
            tenant_id
        )
        return dict(row) if row else None


async def get_subscription_by_mp_id(mp_preapproval_id: str) -> dict[str, Any] | None:
    """Get subscription by Mercado Pago preapproval ID."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM subscriptions WHERE mp_preapproval_id = $1",
            mp_preapproval_id
        )
        return dict(row) if row else None


async def update_subscription(
    subscription_id: UUID,
    **kwargs: Any,
) -> dict[str, Any] | None:
    """Update subscription fields."""
    pool = await get_pool()

    # Build dynamic update query
    fields = []
    values = []
    idx = 1
    
    for key, value in kwargs.items():
        if value is not None:
            fields.append(f"{key} = ${idx}")
            values.append(value)
            idx += 1

    if not fields:
        return await get_subscription_by_id(subscription_id)

    values.append(subscription_id)
    query = f"""
        UPDATE subscriptions 
        SET {', '.join(fields)}, updated_at = NOW()
        WHERE id = ${idx}
        RETURNING *
    """

    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, *values)
        return dict(row) if row else None


async def update_subscription_status(
    subscription_id: UUID,
    status: str,
    cancelled_at: datetime | None = None,
) -> dict[str, Any] | None:
    """Update subscription status."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE subscriptions 
            SET status = $2, cancelled_at = $3, updated_at = NOW()
            WHERE id = $1
            RETURNING *
            """,
            subscription_id, status, cancelled_at
        )
        return dict(row) if row else None


async def update_tenant_plan(
    tenant_id: UUID,
    plan: str,
    subscription_id: UUID | None = None,
) -> bool:
    """Update tenant's plan and subscription reference."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE tenants 
            SET plan = $2, subscription_id = $3, updated_at = NOW()
            WHERE id = $1
            """,
            tenant_id, plan, subscription_id
        )
        return result == "UPDATE 1"


# =============================================================================
# Subscription Payment Operations
# =============================================================================

async def create_payment(
    tenant_id: UUID,
    amount: Decimal,
    status: str,
    subscription_id: UUID | None = None,
    mp_payment_id: str | None = None,
    currency: str = "ARS",
    paid_at: datetime | None = None,
) -> dict[str, Any]:
    """Create a payment record."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO subscription_payments (
                tenant_id, subscription_id, mp_payment_id, amount, currency, status, paid_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING *
            """,
            tenant_id, subscription_id, mp_payment_id, amount, currency, status, paid_at
        )
        return dict(row)


async def get_payment_by_mp_id(mp_payment_id: str) -> dict[str, Any] | None:
    """Get payment by Mercado Pago payment ID."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM subscription_payments WHERE mp_payment_id = $1",
            mp_payment_id
        )
        return dict(row) if row else None


async def get_payments_by_subscription(
    subscription_id: UUID,
    limit: int = 20,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Get payments for a subscription."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM subscription_payments 
            WHERE subscription_id = $1
            ORDER BY created_at DESC
            LIMIT $2 OFFSET $3
            """,
            subscription_id, limit, offset
        )
        return [dict(row) for row in rows]


async def get_payments_by_tenant(
    tenant_id: UUID,
    limit: int = 20,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Get all payments for a tenant."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM subscription_payments 
            WHERE tenant_id = $1
            ORDER BY created_at DESC
            LIMIT $2 OFFSET $3
            """,
            tenant_id, limit, offset
        )
        return [dict(row) for row in rows]


async def update_payment_status(
    payment_id: UUID,
    status: str,
    paid_at: datetime | None = None,
) -> dict[str, Any] | None:
    """Update payment status."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE subscription_payments 
            SET status = $2, paid_at = $3
            WHERE id = $1
            RETURNING *
            """,
            payment_id, status, paid_at
        )
        return dict(row) if row else None


# =============================================================================
# MP Plans Cache Operations
# =============================================================================

async def get_mp_plan_by_pricing(plan_pricing_id: UUID) -> dict[str, Any] | None:
    """Get MP plan by plan_pricing_id."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT * FROM subscription_plans_mp 
            WHERE plan_pricing_id = $1 AND mp_plan_status = 'active'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            plan_pricing_id
        )
        return dict(row) if row else None


async def create_mp_plan(
    plan_pricing_id: UUID,
    mp_plan_id: str,
    synced_price: Decimal,
) -> dict[str, Any]:
    """Create MP plan cache entry."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO subscription_plans_mp (
                plan_pricing_id, mp_plan_id, synced_price
            )
            VALUES ($1, $2, $3)
            RETURNING *
            """,
            plan_pricing_id, mp_plan_id, synced_price
        )
        return dict(row)


async def update_mp_plan_status(
    mp_plan_id: str,
    status: str,
) -> bool:
    """Update MP plan status."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE subscription_plans_mp 
            SET mp_plan_status = $2, last_synced_at = NOW()
            WHERE mp_plan_id = $1
            """,
            mp_plan_id, status
        )
        return result == "UPDATE 1"
