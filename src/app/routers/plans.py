"""Plan pricing management endpoints."""

import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status

from ..middleware.auth import CurrentUser, require_admin
from ..repositories import plan_pricing_repo
from ..schemas.plan_pricing import (
    PlanComparisonResponse,
    PlanPricingAdminListResponse,
    PlanPricingAdminResponse,
    PlanPricingListResponse,
    PlanPricingResponse,
    PlanPricingUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/plans", tags=["Plans"])


# =============================================================================
# Public endpoints
# =============================================================================

@router.get("", response_model=PlanPricingListResponse)
async def get_plans() -> PlanPricingListResponse:
    """
    Get all available plans with pricing.
    
    This endpoint is public and used by:
    - Landing page pricing section
    - Checkout page plan summary
    - Plan comparison features
    """
    plans = await plan_pricing_repo.get_all_plans(active_only=True)
    return PlanPricingListResponse(
        items=[PlanPricingResponse(**p) for p in plans]
    )


@router.get("/{plan_type}", response_model=PlanPricingResponse)
async def get_plan(
    plan_type: Literal["starter", "family", "premium"],
) -> PlanPricingResponse:
    """Get details for a specific plan."""
    plan = await plan_pricing_repo.get_plan_by_type(plan_type)
    
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plan not found: {plan_type}"
        )
    
    return PlanPricingResponse(**plan)


@router.get("/compare/{from_plan}/{to_plan}", response_model=PlanComparisonResponse)
async def compare_plans(
    from_plan: Literal["starter", "family", "premium"],
    to_plan: Literal["starter", "family", "premium"],
) -> PlanComparisonResponse:
    """
    Compare two plans.
    
    Returns the differences between plans including:
    - Price difference
    - Whether it's an upgrade or downgrade
    - Features gained/lost
    """
    if from_plan == to_plan:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot compare a plan with itself"
        )

    result = await plan_pricing_repo.compare_plans(from_plan, to_plan)
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or both plans not found"
        )

    current = PlanPricingResponse(**result["current_plan"])
    target = PlanPricingResponse(**result["target_plan"])

    # Calculate features gained/lost
    current_features = set(current.features)
    target_features = set(target.features)
    features_gained = list(target_features - current_features)
    features_lost = list(current_features - target_features)

    return PlanComparisonResponse(
        current_plan=current,
        target_plan=target,
        price_difference=result["price_difference"],
        is_upgrade=result["is_upgrade"],
        features_gained=features_gained,
        features_lost=features_lost,
    )


# =============================================================================
# Admin endpoints
# =============================================================================

admin_router = APIRouter(prefix="/admin/plans", tags=["Admin - Plans"])


@admin_router.get("", response_model=PlanPricingAdminListResponse)
async def list_plans_admin(
    _: Annotated[CurrentUser, Depends(require_admin)],
) -> PlanPricingAdminListResponse:
    """
    Get all plans with admin metadata (admin only).
    
    Returns additional fields:
    - updated_at: When the plan was last modified
    - updated_by: Who modified it
    """
    plans = await plan_pricing_repo.get_all_plans(active_only=False)
    return PlanPricingAdminListResponse(
        items=[PlanPricingAdminResponse(**p) for p in plans]
    )


@admin_router.get("/{plan_type}", response_model=PlanPricingAdminResponse)
async def get_plan_admin(
    plan_type: Literal["starter", "family", "premium"],
    _: Annotated[CurrentUser, Depends(require_admin)],
) -> PlanPricingAdminResponse:
    """Get plan details with admin metadata (admin only)."""
    plan = await plan_pricing_repo.get_plan_by_type(plan_type)
    
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plan not found: {plan_type}"
        )
    
    return PlanPricingAdminResponse(**plan)


@admin_router.put("/{plan_type}", response_model=PlanPricingAdminResponse)
async def update_plan_pricing(
    plan_type: Literal["starter", "family", "premium"],
    request: PlanPricingUpdate,
    current_user: Annotated[CurrentUser, Depends(require_admin)],
) -> PlanPricingAdminResponse:
    """
    Update plan pricing and configuration (admin only).
    
    Notes:
    - Cannot change the price of the Starter plan (always free)
    - Price changes only affect new subscriptions
    - Existing subscribers keep their current price
    """
    # Validate starter plan constraints
    if plan_type == "starter" and request.price_monthly is not None and request.price_monthly > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot set price for Starter plan - it must remain free"
        )

    # Prepare update data
    update_data = request.model_dump(exclude_unset=True)
    
    if not update_data:
        # No updates provided, just return current plan
        plan = await plan_pricing_repo.get_plan_by_type(plan_type)
        if not plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Plan not found: {plan_type}"
            )
        return PlanPricingAdminResponse(**plan)

    # Update plan
    plan = await plan_pricing_repo.update_plan_pricing(
        plan_type=plan_type,
        updated_by=current_user.user_id,
        **update_data,
    )

    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plan not found: {plan_type}"
        )

    logger.info(f"Updated plan {plan_type} by user {current_user.user_id}: {update_data.keys()}")

    return PlanPricingAdminResponse(**plan)
