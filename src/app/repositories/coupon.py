"""Coupon repository for database operations."""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from ..config.database import get_pool


# =============================================================================
# Coupon Operations
# =============================================================================

async def create_coupon(
    code: str,
    discount_percent: int,
    applicable_plans: list[str],
    description: str | None = None,
    valid_from: datetime | None = None,
    valid_until: datetime | None = None,
    max_redemptions: int | None = None,
    active: bool = True,
    created_by: UUID | None = None,
) -> dict[str, Any]:
    """Create a new coupon."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO coupons (
                code, description, discount_percent, applicable_plans,
                valid_from, valid_until, max_redemptions, active, created_by
            )
            VALUES ($1, $2, $3, $4, COALESCE($5, NOW()), $6, $7, $8, $9)
            RETURNING *
            """,
            code.upper(),
            description,
            discount_percent,
            applicable_plans,
            valid_from,
            valid_until,
            max_redemptions,
            active,
            created_by,
        )
        return dict(row)


async def get_coupon_by_id(coupon_id: UUID) -> dict[str, Any] | None:
    """Get coupon by ID."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM coupons WHERE id = $1",
            coupon_id
        )
        return dict(row) if row else None


async def get_coupon_by_code(code: str) -> dict[str, Any] | None:
    """Get coupon by code."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM coupons WHERE code = $1",
            code.upper()
        )
        return dict(row) if row else None


async def get_all_coupons(
    active_only: bool = False,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """Get all coupons with pagination."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        # Get total count
        if active_only:
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM coupons WHERE active = true"
            )
            rows = await conn.fetch(
                """
                SELECT * FROM coupons 
                WHERE active = true
                ORDER BY created_at DESC
                LIMIT $1 OFFSET $2
                """,
                limit, offset
            )
        else:
            count = await conn.fetchval("SELECT COUNT(*) FROM coupons")
            rows = await conn.fetch(
                """
                SELECT * FROM coupons 
                ORDER BY created_at DESC
                LIMIT $1 OFFSET $2
                """,
                limit, offset
            )
        
        return [dict(row) for row in rows], count


async def update_coupon(
    coupon_id: UUID,
    **kwargs: Any,
) -> dict[str, Any] | None:
    """Update coupon fields."""
    pool = await get_pool()

    # Build dynamic update query
    fields = []
    values = []
    idx = 1

    for key, value in kwargs.items():
        fields.append(f"{key} = ${idx}")
        values.append(value)
        idx += 1

    if not fields:
        return await get_coupon_by_id(coupon_id)

    values.append(coupon_id)
    query = f"""
        UPDATE coupons 
        SET {', '.join(fields)}
        WHERE id = ${idx}
        RETURNING *
    """

    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, *values)
        return dict(row) if row else None


async def delete_coupon(coupon_id: UUID) -> bool:
    """Delete a coupon."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM coupons WHERE id = $1",
            coupon_id
        )
        return result == "DELETE 1"


async def deactivate_coupon(coupon_id: UUID) -> dict[str, Any] | None:
    """Deactivate a coupon (soft delete)."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE coupons 
            SET active = false
            WHERE id = $1
            RETURNING *
            """,
            coupon_id
        )
        return dict(row) if row else None


# =============================================================================
# Coupon Validation
# =============================================================================

async def validate_coupon(
    code: str,
    plan_type: str,
    tenant_id: UUID | None = None,
) -> tuple[bool, dict[str, Any] | None, str | None]:
    """
    Validate if a coupon can be used.
    
    Returns:
        Tuple of (is_valid, coupon_data, error_message)
    """
    pool = await get_pool()

    async with pool.acquire() as conn:
        # Get coupon
        coupon = await conn.fetchrow(
            "SELECT * FROM coupons WHERE code = $1",
            code.upper()
        )

        if not coupon:
            return False, None, "Cupón no encontrado"

        coupon_dict = dict(coupon)

        # Check if active
        if not coupon_dict["active"]:
            return False, coupon_dict, "Cupón inactivo"

        # Check validity dates
        now = datetime.now(coupon_dict["valid_from"].tzinfo) if coupon_dict["valid_from"].tzinfo else datetime.now()
        
        if coupon_dict["valid_from"] and now < coupon_dict["valid_from"]:
            return False, coupon_dict, "Cupón aún no válido"

        if coupon_dict["valid_until"] and now > coupon_dict["valid_until"]:
            return False, coupon_dict, "Cupón expirado"

        # Check max redemptions
        if (
            coupon_dict["max_redemptions"] is not None
            and coupon_dict["current_redemptions"] >= coupon_dict["max_redemptions"]
        ):
            return False, coupon_dict, "Cupón agotado"

        # Check applicable plans
        if plan_type not in coupon_dict["applicable_plans"]:
            return False, coupon_dict, f"Cupón no válido para plan {plan_type}"

        # Check if tenant already used this coupon
        if tenant_id:
            existing = await conn.fetchval(
                """
                SELECT EXISTS(
                    SELECT 1 FROM coupon_redemptions 
                    WHERE coupon_id = $1 AND tenant_id = $2
                )
                """,
                coupon_dict["id"], tenant_id
            )
            if existing:
                return False, coupon_dict, "Ya utilizaste este cupón"

        return True, coupon_dict, None


# =============================================================================
# Coupon Redemption Operations
# =============================================================================

async def create_redemption(
    coupon_id: UUID,
    tenant_id: UUID,
    original_price: Decimal,
    discount_applied: Decimal,
    final_price: Decimal,
    subscription_id: UUID | None = None,
) -> dict[str, Any]:
    """Create a coupon redemption record."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO coupon_redemptions (
                coupon_id, tenant_id, subscription_id,
                original_price, discount_applied, final_price
            )
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING *
            """,
            coupon_id, tenant_id, subscription_id,
            original_price, discount_applied, final_price
        )
        return dict(row)


async def get_redemption_by_tenant_and_coupon(
    tenant_id: UUID,
    coupon_id: UUID,
) -> dict[str, Any] | None:
    """Check if tenant has used a specific coupon."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT * FROM coupon_redemptions 
            WHERE tenant_id = $1 AND coupon_id = $2
            """,
            tenant_id, coupon_id
        )
        return dict(row) if row else None


async def get_redemptions_by_coupon(
    coupon_id: UUID,
    limit: int = 20,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Get all redemptions for a coupon."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT cr.*, t.name as tenant_name
            FROM coupon_redemptions cr
            JOIN tenants t ON cr.tenant_id = t.id
            WHERE cr.coupon_id = $1
            ORDER BY cr.redeemed_at DESC
            LIMIT $2 OFFSET $3
            """,
            coupon_id, limit, offset
        )
        return [dict(row) for row in rows]


async def get_coupon_stats(coupon_id: UUID) -> dict[str, Any]:
    """Get statistics for a coupon."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        stats = await conn.fetchrow(
            """
            SELECT 
                COUNT(*) as total_redemptions,
                COALESCE(SUM(discount_applied), 0) as total_discount_given,
                COALESCE(AVG(discount_applied), 0) as avg_discount
            FROM coupon_redemptions
            WHERE coupon_id = $1
            """,
            coupon_id
        )
        return dict(stats) if stats else {
            "total_redemptions": 0,
            "total_discount_given": Decimal("0"),
            "avg_discount": Decimal("0"),
        }
