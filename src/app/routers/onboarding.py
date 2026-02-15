"""Onboarding endpoints for tenant creation and member management."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..middleware.auth import CurrentUser, get_current_user, validate_tenant_access
from ..repositories.onboarding import get_onboarding_repository
from ..schemas.onboarding import (
    AddMemberRequest,
    MemberResponse,
    OnboardingRequest,
    OnboardingResponse,
    OnboardingStatusResponse,
    PhoneLookupResponse,
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
    - Updates the owner user with their phone
    - Creates user records for each additional member
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
    
    # Update owner's tenant and phone
    await repo.update_user_tenant(current_user.id, tenant_id)
    
    # Process members
    for i, member in enumerate(request.members):
        is_owner_member = (i == 0 and member.role == "admin")
        
        if is_owner_member:
            # First admin = the owner. Update their existing user record with phone.
            await repo.update_user_phone(current_user.id, member.phone)
        else:
            # Additional members: create new user records
            await repo.create_member(
                tenant_id=tenant_id,
                phone=member.phone,
                display_name=member.name,
                role=member.role,
                email=member.email,
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
# Phone Lookup (Public - used by bot)
# ============================================================================

@router.get("/phone/lookup", response_model=PhoneLookupResponse)
async def lookup_phone(
    phone: str = Query(..., description="Phone number in E.164 format"),
) -> PhoneLookupResponse:
    """
    Look up tenant by phone number.
    
    This endpoint is used by the bot for multitenancy resolution.
    It's intentionally public (no auth) so the bot can call it.
    Searches the users table directly.
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


# ============================================================================
# Member Management Endpoints
# ============================================================================

@router.get(
    "/tenants/{tenant_id}/members",
    response_model=list[MemberResponse],
)
async def list_members(
    tenant_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> list[MemberResponse]:
    """List all members of a tenant."""
    validate_tenant_access(current_user.tenant_id, tenant_id)
    
    repo = get_onboarding_repository()
    members = await repo.get_members_by_tenant(tenant_id)
    
    return [
        MemberResponse(
            id=m["id"],
            phone=m.get("phone"),
            email=m.get("email"),
            display_name=m.get("display_name"),
            role=m.get("role", "member"),
            phone_verified=m.get("phone_verified", False),
            email_verified=m.get("email_verified", False),
            avatar_url=m.get("avatar_url"),
            is_active=m.get("is_active", True),
            created_at=m.get("created_at"),
        )
        for m in members
    ]


@router.post(
    "/tenants/{tenant_id}/members",
    response_model=MemberResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_member(
    tenant_id: UUID,
    request: AddMemberRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> MemberResponse:
    """Add a new member to a tenant."""
    validate_tenant_access(current_user.tenant_id, tenant_id)
    
    repo = get_onboarding_repository()
    
    # Check if phone already exists
    if await repo.check_phone_exists(request.phone):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Phone number is already registered",
        )
    
    user_id = await repo.create_member(
        tenant_id=tenant_id,
        phone=request.phone,
        display_name=request.display_name,
        role=request.role,
        email=request.email,
    )
    
    return MemberResponse(
        id=user_id,
        phone=request.phone,
        email=request.email,
        display_name=request.display_name,
        role=request.role,
    )


@router.delete(
    "/tenants/{tenant_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_member(
    tenant_id: UUID,
    user_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> None:
    """Remove a member from a tenant (soft delete)."""
    validate_tenant_access(current_user.tenant_id, tenant_id)
    
    # Can't remove yourself
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove yourself",
        )
    
    repo = get_onboarding_repository()
    removed = await repo.remove_member(user_id, tenant_id)
    
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found",
        )
