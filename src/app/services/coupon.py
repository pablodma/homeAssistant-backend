"""Coupon service for business logic."""

import logging
import secrets
import string
from decimal import Decimal
from uuid import UUID

from ..repositories import coupon_repo, plan_pricing_repo
from ..schemas.coupon import (
    CouponCreate,
    CouponListResponse,
    CouponResponse,
    CouponStatsResponse,
    CouponUpdate,
    CouponValidateRequest,
    CouponValidateResponse,
)

logger = logging.getLogger(__name__)


class CouponService:
    """Service for managing discount coupons."""

    @staticmethod
    def generate_coupon_code(prefix: str = "PROMO", length: int = 6) -> str:
        """
        Generate a random coupon code.
        
        Args:
            prefix: Prefix for the code
            length: Length of random part
            
        Returns:
            Generated code like PROMO2026ABC
        """
        chars = string.ascii_uppercase + string.digits
        random_part = "".join(secrets.choice(chars) for _ in range(length))
        return f"{prefix}{random_part}"

    async def create_coupon(
        self,
        data: CouponCreate,
        created_by: UUID | None = None,
    ) -> CouponResponse:
        """
        Create a new coupon.
        
        Args:
            data: Coupon creation data
            created_by: User ID who created the coupon
            
        Returns:
            Created coupon
        """
        # Verify code is unique
        existing = await coupon_repo.get_coupon_by_code(data.code)
        if existing:
            raise ValueError(f"Coupon code already exists: {data.code}")

        # Create coupon
        coupon = await coupon_repo.create_coupon(
            code=data.code,
            description=data.description,
            discount_percent=data.discount_percent,
            applicable_plans=data.applicable_plans,
            valid_from=data.valid_from,
            valid_until=data.valid_until,
            max_redemptions=data.max_redemptions,
            active=data.active,
            created_by=created_by,
        )

        logger.info(f"Created coupon: {data.code} with {data.discount_percent}% discount")
        return CouponResponse(**coupon)

    async def get_coupon(self, coupon_id: UUID) -> CouponResponse | None:
        """Get a coupon by ID."""
        coupon = await coupon_repo.get_coupon_by_id(coupon_id)
        return CouponResponse(**coupon) if coupon else None

    async def get_coupon_by_code(self, code: str) -> CouponResponse | None:
        """Get a coupon by code."""
        coupon = await coupon_repo.get_coupon_by_code(code)
        return CouponResponse(**coupon) if coupon else None

    async def list_coupons(
        self,
        active_only: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> CouponListResponse:
        """List all coupons."""
        coupons, total = await coupon_repo.get_all_coupons(
            active_only=active_only,
            limit=limit,
            offset=offset,
        )
        return CouponListResponse(
            items=[CouponResponse(**c) for c in coupons],
            total=total,
        )

    async def update_coupon(
        self,
        coupon_id: UUID,
        data: CouponUpdate,
    ) -> CouponResponse | None:
        """Update a coupon."""
        update_data = data.model_dump(exclude_unset=True)
        if not update_data:
            coupon = await coupon_repo.get_coupon_by_id(coupon_id)
            return CouponResponse(**coupon) if coupon else None

        coupon = await coupon_repo.update_coupon(coupon_id, **update_data)
        if coupon:
            logger.info(f"Updated coupon {coupon_id}: {update_data.keys()}")
        return CouponResponse(**coupon) if coupon else None

    async def delete_coupon(self, coupon_id: UUID) -> bool:
        """
        Delete a coupon.
        
        Note: This is a hard delete. Use deactivate for soft delete.
        """
        success = await coupon_repo.delete_coupon(coupon_id)
        if success:
            logger.info(f"Deleted coupon: {coupon_id}")
        return success

    async def deactivate_coupon(self, coupon_id: UUID) -> CouponResponse | None:
        """Deactivate a coupon (soft delete)."""
        coupon = await coupon_repo.deactivate_coupon(coupon_id)
        if coupon:
            logger.info(f"Deactivated coupon: {coupon_id}")
        return CouponResponse(**coupon) if coupon else None

    async def validate_coupon(
        self,
        data: CouponValidateRequest,
        tenant_id: UUID | None = None,
    ) -> CouponValidateResponse:
        """
        Validate if a coupon can be used.
        
        Args:
            data: Validation request with code and plan type
            tenant_id: Optional tenant ID to check previous usage
            
        Returns:
            Validation response with status and details
        """
        is_valid, coupon, error = await coupon_repo.validate_coupon(
            code=data.code,
            plan_type=data.plan_type,
            tenant_id=tenant_id,
        )

        if is_valid and coupon:
            return CouponValidateResponse(
                valid=True,
                discount_percent=coupon["discount_percent"],
                description=coupon.get("description"),
            )
        
        return CouponValidateResponse(
            valid=False,
            error=error or "Invalid coupon",
        )

    async def calculate_discounted_price(
        self,
        plan_type: str,
        coupon_code: str | None = None,
        tenant_id: UUID | None = None,
    ) -> tuple[Decimal, Decimal, int | None]:
        """
        Calculate discounted price for a plan.
        
        Args:
            plan_type: Plan type to get price for
            coupon_code: Optional coupon code
            tenant_id: Optional tenant ID for validation
            
        Returns:
            Tuple of (original_price, final_price, discount_percent)
        """
        # Get plan price
        plan = await plan_pricing_repo.get_plan_by_type(plan_type)
        if not plan:
            raise ValueError(f"Plan not found: {plan_type}")

        original_price = Decimal(str(plan["price_monthly"]))
        final_price = original_price
        discount_percent = None

        # Apply coupon if provided
        if coupon_code:
            is_valid, coupon, _ = await coupon_repo.validate_coupon(
                code=coupon_code,
                plan_type=plan_type,
                tenant_id=tenant_id,
            )

            if is_valid and coupon:
                discount_percent = coupon["discount_percent"]
                discount_amount = original_price * Decimal(discount_percent) / 100
                final_price = original_price - discount_amount

        return original_price, final_price, discount_percent

    async def get_coupon_stats(self, coupon_id: UUID) -> CouponStatsResponse | None:
        """Get statistics for a coupon."""
        coupon = await coupon_repo.get_coupon_by_id(coupon_id)
        if not coupon:
            return None

        stats = await coupon_repo.get_coupon_stats(coupon_id)
        redemptions = await coupon_repo.get_redemptions_by_coupon(coupon_id, limit=10)

        return CouponStatsResponse(
            coupon_id=coupon_id,
            code=coupon["code"],
            total_redemptions=stats["total_redemptions"],
            total_discount_given=stats["total_discount_given"],
            recent_redemptions=redemptions,
        )


# Singleton instance
_coupon_service: CouponService | None = None


def get_coupon_service() -> CouponService:
    """Get coupon service instance."""
    global _coupon_service
    if _coupon_service is None:
        _coupon_service = CouponService()
    return _coupon_service
