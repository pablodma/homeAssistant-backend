"""Coupon management endpoints."""

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from ..middleware.auth import CurrentUser, get_current_user_optional

# Default admin UUID for unauthenticated requests (internal admin)
DEFAULT_ADMIN_ID = UUID("00000000-0000-0000-0000-000000000001")
from ..schemas.coupon import (
    CouponCreate,
    CouponListResponse,
    CouponResponse,
    CouponStatsResponse,
    CouponUpdate,
    CouponValidateRequest,
    CouponValidateResponse,
)
from ..services.coupon import CouponService, get_coupon_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/coupons", tags=["Coupons"])


# =============================================================================
# Public endpoints
# =============================================================================

@router.post("/validate", response_model=CouponValidateResponse)
async def validate_coupon(
    request: CouponValidateRequest,
    current_user: Annotated[CurrentUser | None, Depends(get_current_user_optional)] = None,
) -> CouponValidateResponse:
    """
    Validate if a coupon code is valid for a plan.
    
    This is used in the checkout flow to validate the promotional code
    before proceeding with payment.
    """
    service = get_coupon_service()
    
    # Get tenant_id if user is authenticated
    tenant_id = current_user.tenant_id if current_user else None
    
    return await service.validate_coupon(
        data=request,
        tenant_id=tenant_id,
    )


@router.get("/generate-code", response_model=dict)
async def generate_coupon_code(
    prefix: str = "PROMO",
    current_user: Annotated[CurrentUser | None, Depends(get_current_user_optional)] = None,
) -> dict:
    """Generate a random coupon code."""
    code = CouponService.generate_coupon_code(prefix=prefix)
    return {"code": code}


# =============================================================================
# Admin endpoints
# =============================================================================

admin_router = APIRouter(prefix="/admin/coupons", tags=["Admin - Coupons"])


@admin_router.get("", response_model=CouponListResponse)
async def list_coupons(
    current_user: Annotated[CurrentUser | None, Depends(get_current_user_optional)] = None,
    active_only: bool = False,
    limit: int = 100,
    offset: int = 0,
) -> CouponListResponse:
    """
    List all coupons (admin only).
    
    Args:
        active_only: Filter to show only active coupons
        limit: Maximum number of results
        offset: Pagination offset
    """
    service = get_coupon_service()
    return await service.list_coupons(
        active_only=active_only,
        limit=limit,
        offset=offset,
    )


@admin_router.post("", response_model=CouponResponse, status_code=status.HTTP_201_CREATED)
async def create_coupon(
    request: CouponCreate,
    current_user: Annotated[CurrentUser | None, Depends(get_current_user_optional)] = None,
) -> CouponResponse:
    """
    Create a new coupon.
    
    Required fields:
    - code: Unique coupon code (will be converted to uppercase)
    - discount_percent: Discount percentage (1-100)
    - applicable_plans: List of plans this coupon applies to ["family", "premium"]
    
    Optional fields:
    - description: Human-readable description
    - valid_from: When the coupon becomes valid (default: now)
    - valid_until: When the coupon expires (default: never)
    - max_redemptions: Maximum number of uses (default: unlimited)
    - active: Whether the coupon is active (default: true)
    """
    service = get_coupon_service()
    user_id = current_user.id if current_user else DEFAULT_ADMIN_ID
    
    try:
        return await service.create_coupon(
            data=request,
            created_by=user_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@admin_router.get("/{coupon_id}", response_model=CouponResponse)
async def get_coupon(
    coupon_id: UUID,
    current_user: Annotated[CurrentUser | None, Depends(get_current_user_optional)] = None,
) -> CouponResponse:
    """Get coupon details by ID (admin only)."""
    service = get_coupon_service()
    coupon = await service.get_coupon(coupon_id)
    
    if not coupon:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Coupon not found"
        )
    
    return coupon


@admin_router.get("/{coupon_id}/stats", response_model=CouponStatsResponse)
async def get_coupon_stats(
    coupon_id: UUID,
    current_user: Annotated[CurrentUser | None, Depends(get_current_user_optional)] = None,
) -> CouponStatsResponse:
    """
    Get coupon statistics (admin only).
    
    Returns:
    - Total redemptions
    - Total discount given
    - Recent redemptions list
    """
    service = get_coupon_service()
    stats = await service.get_coupon_stats(coupon_id)
    
    if not stats:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Coupon not found"
        )
    
    return stats


@admin_router.patch("/{coupon_id}", response_model=CouponResponse)
async def update_coupon(
    coupon_id: UUID,
    request: CouponUpdate,
    current_user: Annotated[CurrentUser | None, Depends(get_current_user_optional)] = None,
) -> CouponResponse:
    """
    Update a coupon (admin only).
    
    Only the following fields can be updated:
    - description
    - valid_until
    - max_redemptions
    - active
    """
    service = get_coupon_service()
    coupon = await service.update_coupon(coupon_id, request)
    
    if not coupon:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Coupon not found"
        )
    
    return coupon


@admin_router.delete("/{coupon_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_coupon(
    coupon_id: UUID,
    current_user: Annotated[CurrentUser | None, Depends(get_current_user_optional)] = None,
    soft: bool = True,
) -> None:
    """
    Delete a coupon (admin only).
    
    Args:
        soft: If true, deactivates the coupon. If false, permanently deletes it.
    """
    service = get_coupon_service()
    
    if soft:
        result = await service.deactivate_coupon(coupon_id)
    else:
        result = await service.delete_coupon(coupon_id)
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Coupon not found"
        )
