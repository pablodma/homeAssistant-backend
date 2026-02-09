"""Onboarding endpoints for tenant creation and phone management."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..middleware.auth import CurrentUser, get_current_user, validate_tenant_access
from ..repositories.onboarding import get_onboarding_repository
from ..schemas.onboarding import (
    OnboardingRequest,
    OnboardingResponse,
    OnboardingStatusResponse,
    PhoneLookupResponse,
    PhoneTenantMapping,
    RegisterPhoneRequest,
)

router = APIRouter(tags=["Onboarding"])


@router.get("/onboarding/status", response_model=OnboardingStatusResponse)
async def get_onboarding_status(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> OnboardingStatusResponse:
    """
    Check if current user has completed onboarding.
    
    Returns tenant info if onboarding is complete.
    """
    repo = get_onboarding_repository()
    tenant_info = await repo.get_user_tenant(current_user.id)
    
    if not tenant_info:
        return OnboardingStatusResponse(
            onboarding_completed=False,
            tenant_id=None,
            home_name=None,
        )
    
    return OnboardingStatusResponse(
        onboarding_completed=tenant_info.get("onboarding_completed", False),
        tenant_id=tenant_info.get("tenant_id"),
        home_name=tenant_info.get("home_name"),
    )


@router.post("/onboarding", response_model=OnboardingResponse, status_code=status.HTTP_201_CREATED)
async def complete_onboarding(
    request: OnboardingRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> OnboardingResponse:
    """
    Complete onboarding by creating a new tenant.
    
    - Creates a new tenant with the provided settings
    - Associates the current user as owner
    - Registers all phone numbers
    - Creates default budget categories
    """
    repo = get_onboarding_repository()
    
    # Check if any phone is already registered
    for member in request.members:
        if await repo.check_phone_exists(member.phone):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Phone {member.phone} is already registered to another household",
            )
    
    # Create the tenant
    tenant_id = await repo.create_tenant(
        home_name=request.home_name,
        plan=request.plan,
        owner_user_id=current_user.id,
        timezone=request.timezone,
        language=request.language,
        currency=request.currency,
    )
    
    # Update user's tenant
    await repo.update_user_tenant(current_user.id, tenant_id)
    
    # Register all phone numbers
    for i, member in enumerate(request.members):
        # First admin member is primary
        is_primary = (i == 0 and member.role == "admin") or (
            member.role == "admin" and not any(
                m.role == "admin" for m in request.members[:i]
            )
        )
        
        await repo.register_phone(
            phone=member.phone,
            tenant_id=tenant_id,
            user_id=current_user.id if is_primary else None,
            display_name=member.name,
            is_primary=is_primary,
        )
    
    # Create default budget categories
    await repo.create_default_budget_categories(tenant_id)
    
    return OnboardingResponse(
        tenant_id=tenant_id,
        home_name=request.home_name,
        plan=request.plan,
        members_count=len(request.members),
    )


# ============================================================================
# Phone Management Endpoints
# ============================================================================

@router.get("/phone/lookup", response_model=PhoneLookupResponse)
async def lookup_phone(
    phone: str = Query(..., description="Phone number in E.164 format"),
) -> PhoneLookupResponse:
    """
    Look up tenant by phone number.
    
    This endpoint is used by the bot for multitenancy resolution.
    It's intentionally public (no auth) so the bot can call it.
    """
    repo = get_onboarding_repository()
    result = await repo.get_tenant_by_phone(phone)
    
    if not result:
        return PhoneLookupResponse(
            found=False,
            tenant_id=None,
            user_name=None,
            home_name=None,
        )
    
    return PhoneLookupResponse(
        found=True,
        tenant_id=result["tenant_id"],
        user_name=result.get("user_name"),
        home_name=result.get("home_name"),
    )


@router.get(
    "/tenants/{tenant_id}/phones",
    response_model=list[PhoneTenantMapping],
)
async def list_tenant_phones(
    tenant_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> list[PhoneTenantMapping]:
    """List all phones registered to a tenant."""
    validate_tenant_access(current_user.tenant_id, tenant_id)
    
    repo = get_onboarding_repository()
    phones = await repo.get_phones_by_tenant(tenant_id)
    
    return [
        PhoneTenantMapping(
            phone=p["phone"],
            tenant_id=tenant_id,
            user_id=p.get("user_id"),
            display_name=p.get("display_name"),
            is_primary=p.get("is_primary", False),
            verified_at=p.get("verified_at"),
        )
        for p in phones
    ]


@router.post(
    "/tenants/{tenant_id}/phones",
    response_model=PhoneTenantMapping,
    status_code=status.HTTP_201_CREATED,
)
async def register_phone(
    tenant_id: UUID,
    request: RegisterPhoneRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> PhoneTenantMapping:
    """Register a new phone number to a tenant."""
    validate_tenant_access(current_user.tenant_id, tenant_id)
    
    repo = get_onboarding_repository()
    
    # Check if phone already exists
    if await repo.check_phone_exists(request.phone):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Phone number is already registered",
        )
    
    await repo.register_phone(
        phone=request.phone,
        tenant_id=tenant_id,
        user_id=None,  # Can be linked later
        display_name=request.display_name,
        is_primary=request.is_primary,
    )
    
    return PhoneTenantMapping(
        phone=request.phone,
        tenant_id=tenant_id,
        user_id=None,
        display_name=request.display_name,
        is_primary=request.is_primary,
        verified_at=None,
    )


@router.delete("/tenants/{tenant_id}/phones/{phone}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_phone(
    tenant_id: UUID,
    phone: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> None:
    """Remove a phone number from a tenant."""
    validate_tenant_access(current_user.tenant_id, tenant_id)
    
    repo = get_onboarding_repository()
    deleted = await repo.delete_phone_mapping(phone, tenant_id)
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Phone not found",
        )
