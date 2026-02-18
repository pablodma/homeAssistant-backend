"""Onboarding endpoints for tenant creation and member management."""

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..config.database import get_pool

from ..middleware.auth import CurrentUser, check_tenant_access, get_current_user, require_service_token
from ..repositories.agent_onboarding import get_agent_onboarding_repository
from ..repositories.onboarding import get_onboarding_repository
from ..repositories.pending_registration import get_pending_registration_repository
from ..schemas.onboarding import (
    AddMemberRequest,
    AgentOnboardingCompleteRequest,
    AgentOnboardingCompleteResponse,
    AgentOnboardingStatusResponse,
    BotInviteMemberRequest,
    BotInviteMemberResponse,
    MemberResponse,
    OnboardingRequest,
    OnboardingResponse,
    OnboardingStatusResponse,
    PhoneLookupResponse,
    SetupCompleteRequest,
    SetupCompleteResponse,
    SubscriptionUsageResponse,
    WhatsAppPendingRequest,
    WhatsAppPendingResponse,
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
# Phone Lookup (Service token required - used by bot)
# ============================================================================

@router.get("/phone/lookup", response_model=PhoneLookupResponse)
async def lookup_phone(
    phone: str = Query(..., description="Phone number in E.164 format"),
    _service_user: Annotated[CurrentUser, Depends(require_service_token)] = None,
) -> PhoneLookupResponse:
    """Look up tenant by phone number.

    Used by the bot for multitenancy resolution.
    Requires service token (role=system).
    """
    repo = get_onboarding_repository()
    result = await repo.get_tenant_by_phone(phone)
    
    if not result:
        return PhoneLookupResponse(
            found=False,
            tenant_id=None,
            user_name=None,
            home_name=None,
            onboarding_completed=None,
        )
    
    return PhoneLookupResponse(
        found=True,
        tenant_id=result["tenant_id"],
        user_name=result.get("user_name"),
        home_name=result.get("home_name"),
        onboarding_completed=result.get("onboarding_completed", False),
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
    check_tenant_access(current_user, tenant_id)
    
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
    check_tenant_access(current_user, tenant_id)
    
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
    check_tenant_access(current_user, tenant_id)
    
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


# ============================================================================
# Bot Member Invitation (used by bot via service token)
# ============================================================================


@router.post(
    "/tenants/{tenant_id}/members/bot",
    response_model=BotInviteMemberResponse,
    status_code=status.HTTP_201_CREATED,
)
async def bot_invite_member(
    tenant_id: UUID,
    request: BotInviteMemberRequest,
    _service_user: Annotated[CurrentUser, Depends(require_service_token)],
) -> BotInviteMemberResponse:
    """
    Invite a member to a tenant via bot.

    Called by the SubscriptionAgent to add a WhatsApp number to a household.
    Validates plan member limits before adding.

    Requires service token (role=system).
    """
    logger = logging.getLogger(__name__)
    repo = get_onboarding_repository()
    pool = await get_pool()

    # Check if phone is already registered
    if await repo.check_phone_exists(request.phone):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ese número ya está registrado en otro hogar",
        )

    # Get current member count
    members = await repo.get_members_by_tenant(tenant_id)
    current_count = len(members)

    # Get plan member limit
    tenant_row = await pool.fetchrow(
        "SELECT plan FROM tenants WHERE id = $1",
        tenant_id,
    )
    if not tenant_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hogar no encontrado",
        )

    plan = tenant_row["plan"]
    pricing_row = await pool.fetchrow(
        "SELECT max_members FROM plan_pricing WHERE plan_type = $1",
        plan,
    )

    if pricing_row and pricing_row["max_members"] is not None:
        max_members = pricing_row["max_members"]
        if current_count >= max_members:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Tu plan {plan} permite hasta {max_members} miembros. "
                       f"Ya tenés {current_count}. Hacé upgrade para sumar más.",
            )

    # Create member with temporary display_name
    normalized_phone = repo._normalize_phone(request.phone)
    user_id = await repo.create_member(
        tenant_id=tenant_id,
        phone=normalized_phone,
        display_name="Miembro",
        role="member",
    )

    logger.info(
        f"Bot invited member: tenant={tenant_id}, phone={normalized_phone}, user={user_id}"
    )

    return BotInviteMemberResponse(
        success=True,
        member_id=user_id,
        phone=normalized_phone,
    )


# ============================================================================
# WhatsApp Onboarding (used by bot via service token)
# ============================================================================


@router.patch(
    "/tenants/{tenant_id}/setup",
    response_model=SetupCompleteResponse,
)
async def complete_tenant_setup(
    tenant_id: UUID,
    request: SetupCompleteRequest,
    _service_user: Annotated[CurrentUser, Depends(require_service_token)],
) -> SetupCompleteResponse:
    """
    Complete home setup after payment confirmation.

    Called by the bot when a new user configures their home name
    after successful payment. Sets home_name and marks onboarding_completed=true.

    Requires service token (role=system).
    """
    logger = logging.getLogger(__name__)
    pool = await get_pool()

    # Verify tenant exists
    tenant = await pool.fetchrow(
        "SELECT id, onboarding_completed FROM tenants WHERE id = $1",
        tenant_id,
    )
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hogar no encontrado",
        )

    # Update home_name and mark onboarding as complete
    await pool.execute(
        """
        UPDATE tenants
        SET home_name = $1, name = $1, onboarding_completed = true, updated_at = NOW()
        WHERE id = $2
        """,
        request.home_name,
        tenant_id,
    )

    logger.info(
        f"Tenant setup completed: tenant={tenant_id}, home_name={request.home_name}"
    )

    return SetupCompleteResponse(
        tenant_id=tenant_id,
        home_name=request.home_name,
    )


@router.post(
    "/onboarding/whatsapp/pending",
    response_model=WhatsAppPendingResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_pending_registration(
    request: WhatsAppPendingRequest,
    _service_user: Annotated[CurrentUser, Depends(require_service_token)],
) -> WhatsAppPendingResponse:
    """
    Create a pending registration for any plan (all plans go through checkout).

    Called by the bot when a user chooses a plan via WhatsApp.
    Stores registration data, creates a Lemon Squeezy checkout,
    and returns the checkout URL. home_name is optional (collected post-payment).

    The LS webhook will create the actual tenant on payment confirmation.

    Requires service token (role=system).
    """
    logger = logging.getLogger(__name__)

    repo = get_onboarding_repository()
    pending_repo = get_pending_registration_repository()

    # Check if phone is already registered
    if await repo.check_phone_exists(request.phone):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este número ya está registrado en otro hogar",
        )

    try:
        # Normalize phone
        normalized_phone = repo._normalize_phone(request.phone)

        # Create pending registration
        pending = await pending_repo.create(
            phone=normalized_phone,
            display_name=request.display_name,
            home_name=request.home_name,
            plan_type=request.plan_type,
            coupon_code=request.coupon_code,
        )

        # Generate Lemon Squeezy checkout
        from ..config.lemonsqueezy import PLAN_VARIANT_MAP, get_ls_client
        from ..config import get_settings as _get_settings

        ls_client = get_ls_client()
        settings = _get_settings()

        variant_id = PLAN_VARIANT_MAP.get(request.plan_type)
        if not variant_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Plan no disponible: {request.plan_type}",
            )

        checkout_url = None
        if ls_client.is_configured:
            checkout = await ls_client.create_checkout(
                variant_id=variant_id,
                email=f"{normalized_phone}@whatsapp.placeholder",
                custom_data={
                    "pending_registration_id": str(pending["id"]),
                    "phone": normalized_phone,
                    "plan_type": request.plan_type,
                    "source": "whatsapp",
                },
                redirect_url=f"{settings.frontend_url}/checkout/callback",
                discount_code=request.coupon_code,
            )

            if checkout:
                await pending_repo.update_checkout_id(
                    pending["id"], checkout["id"]
                )
                checkout_url = checkout["url"]
            else:
                logger.error(
                    f"Failed to create LS checkout for pending registration {pending['id']}"
                )
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="No se pudo generar el link de pago",
                )
        else:
            logger.error("Lemon Squeezy not configured")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Sistema de pagos no disponible",
            )

        return WhatsAppPendingResponse(
            pending_id=pending["id"],
            checkout_url=checkout_url,
            plan_type=request.plan_type,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error creating pending registration: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al procesar la solicitud",
        )


# ============================================================================
# Agent First-Time Onboarding (used by bot via service token)
# ============================================================================


@router.get(
    "/agent-onboarding/status",
    response_model=AgentOnboardingStatusResponse,
)
async def get_agent_onboarding_status(
    phone: str = Query(..., description="Phone number"),
    agent: str = Query(..., description="Agent name (finance, calendar, etc.)"),
    _service_user: Annotated[CurrentUser, Depends(require_service_token)] = None,
) -> AgentOnboardingStatusResponse:
    """Check if a user has completed first-time onboarding for an agent.

    Used by the bot to detect first-time use per agent.
    Requires service token (role=system).
    """
    repo = get_agent_onboarding_repository()
    is_first_time = await repo.get_status(phone, agent)

    return AgentOnboardingStatusResponse(
        is_first_time=is_first_time,
        agent_name=agent,
    )


@router.post(
    "/agent-onboarding/complete",
    response_model=AgentOnboardingCompleteResponse,
)
async def complete_agent_onboarding(
    request: AgentOnboardingCompleteRequest,
    _service_user: Annotated[CurrentUser, Depends(require_service_token)],
) -> AgentOnboardingCompleteResponse:
    """Mark agent first-time onboarding as completed for a user.

    Called by the bot when a user finishes the guided setup for an agent.
    Requires service token (role=system).
    """
    repo = get_agent_onboarding_repository()
    success = await repo.complete(request.phone, request.agent_name)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado",
        )

    return AgentOnboardingCompleteResponse(
        success=True,
        agent_name=request.agent_name,
    )
