"""Plan pricing management endpoints."""

import logging
from typing import Annotated, Literal
from uuid import UUID

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
# Services catalog (for plan configurator)
# =============================================================================

SERVICES_CATALOG = [
    {"id": "reminder", "name": "Recordatorios"},
    {"id": "shopping", "name": "Listas de compras"},
    {"id": "finance", "name": "Presupuesto y Gastos"},
    {"id": "calendar", "name": "Calendario"},
    {"id": "vehicle", "name": "Gestión de Vehículos"},
]

services_admin_router = APIRouter(prefix="/admin/services", tags=["Admin - Services"])


@services_admin_router.get("")
async def get_services() -> list[dict[str, str]]:
    """Get catalog of available services for plan configurator."""
    return SERVICES_CATALOG


# =============================================================================
# Admin endpoints
# =============================================================================

admin_router = APIRouter(prefix="/admin/plans", tags=["Admin - Plans"])


@admin_router.get("", response_model=PlanPricingAdminListResponse)
async def list_plans_admin(
    current_user: Annotated[CurrentUser, Depends(require_admin)],
) -> PlanPricingAdminListResponse:
    """Get all plans with admin metadata."""
    plans = await plan_pricing_repo.get_all_plans(active_only=False)
    return PlanPricingAdminListResponse(
        items=[PlanPricingAdminResponse(**p) for p in plans]
    )


@admin_router.get("/{plan_type}", response_model=PlanPricingAdminResponse)
async def get_plan_admin(
    plan_type: Literal["starter", "family", "premium"],
    current_user: Annotated[CurrentUser, Depends(require_admin)],
) -> PlanPricingAdminResponse:
    """Get plan details with admin metadata."""
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
    user_id = current_user.id

    try:
        plan = await plan_pricing_repo.update_plan_pricing(
            plan_type=plan_type,
            updated_by=user_id,
            **update_data,
        )
    except Exception as e:
        # If FK violation on updated_by (user deleted), retry without it
        if "foreign key" in str(e).lower() and "updated_by" in str(e).lower():
            logger.warning(f"User {user_id} not found in users table, updating plan without updated_by")
            plan = await plan_pricing_repo.update_plan_pricing(
                plan_type=plan_type,
                updated_by=None,
                **update_data,
            )
        else:
            raise

    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plan not found: {plan_type}"
        )

    logger.info(f"Updated plan {plan_type} by user {user_id}: {update_data.keys()}")

    return PlanPricingAdminResponse(**plan)
