"""Subscription management endpoints."""

import logging
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel

from ..config.lemonsqueezy import get_ls_client
from ..middleware.auth import CurrentUser, get_current_user, require_service_token
from ..repositories import subscription_repo
from ..schemas.onboarding import SubscriptionUsageResponse
from ..schemas.subscription import (
    LemonSqueezyWebhookResponse,
    PaymentListResponse,
    SubscriptionCancelRequest,
    SubscriptionCancelResponse,
    SubscriptionCreate,
    SubscriptionCreateResponse,
    SubscriptionPaymentResponse,
    SubscriptionResponse,
    SubscriptionStatusResponse,
)
from ..services.subscription import get_subscription_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])


@router.post("", response_model=SubscriptionCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_subscription(
    request: SubscriptionCreate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> SubscriptionCreateResponse:
    """
    Create a new subscription for the current tenant.

    This endpoint:
    1. Validates the plan type and optional coupon code
    2. Creates a subscription record in our database
    3. Creates a checkout in Lemon Squeezy
    4. Returns the checkout URL for payment
    """
    if not current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User must belong to a tenant to subscribe",
        )

    service = get_subscription_service()

    try:
        result = await service.create_subscription(
            tenant_id=current_user.tenant_id,
            plan_type=request.plan_type,
            payer_email=request.payer_email,
            coupon_code=request.coupon_code,
            redirect_url=request.redirect_url,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except RuntimeError as e:
        logger.error("Payment provider error creating subscription", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Error al comunicarse con el proveedor de pagos. Intentá nuevamente.",
        )
    except Exception as e:
        logger.exception(f"Unexpected error creating subscription: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno al crear la suscripción. Por favor, intentá nuevamente.",
        )


@router.get("/me", response_model=SubscriptionStatusResponse)
async def get_my_subscription(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> SubscriptionStatusResponse:
    """Get subscription status for the current tenant."""
    if not current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User must belong to a tenant",
        )

    service = get_subscription_service()
    return await service.get_subscription_status(
        tenant_id=current_user.tenant_id,
        current_plan=current_user.tenant_plan or "starter",
    )


@router.post("/cancel", response_model=SubscriptionCancelResponse)
async def cancel_subscription(
    request: SubscriptionCancelRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> SubscriptionCancelResponse:
    """Cancel the current tenant's subscription."""
    if not current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User must belong to a tenant",
        )

    service = get_subscription_service()
    success, message = await service.cancel_subscription(
        tenant_id=current_user.tenant_id,
        reason=request.reason,
    )

    return SubscriptionCancelResponse(
        success=success,
        message=message,
    )


@router.post("/pause", response_model=dict)
async def pause_subscription(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict:
    """Pause the current tenant's subscription."""
    if not current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User must belong to a tenant",
        )

    service = get_subscription_service()
    success, message = await service.pause_subscription(
        tenant_id=current_user.tenant_id,
    )

    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

    return {"success": success, "message": message}


@router.get("/payments", response_model=PaymentListResponse)
async def get_my_payments(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    limit: int = 20,
    offset: int = 0,
) -> PaymentListResponse:
    """Get payment history for the current tenant."""
    if not current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User must belong to a tenant",
        )

    payments = await subscription_repo.get_payments_by_tenant(
        tenant_id=current_user.tenant_id,
        limit=limit,
        offset=offset,
    )

    return PaymentListResponse(
        items=[SubscriptionPaymentResponse(**p) for p in payments],
        total=len(payments),
    )


@router.post("/sync", response_model=SubscriptionResponse | None)
async def sync_subscription(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> SubscriptionResponse | None:
    """
    Sync subscription status with Lemon Squeezy.

    Call this if you suspect local data is out of sync.
    """
    if not current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User must belong to a tenant",
        )

    subscription = await subscription_repo.get_subscription_by_tenant(current_user.tenant_id)
    if not subscription:
        return None

    service = get_subscription_service()
    updated = await service.sync_subscription_status(subscription["id"])
    return SubscriptionResponse(**updated) if updated else None


# =============================================================================
# Bot-facing endpoints (service token auth)
# =============================================================================


@router.get("/usage/{tenant_id}", response_model=SubscriptionUsageResponse)
async def get_subscription_usage(
    tenant_id: UUID,
    _service_user: Annotated[CurrentUser, Depends(require_service_token)],
) -> SubscriptionUsageResponse:
    """
    Get subscription usage stats for a tenant.

    Called by the bot's SubscriptionAgent. Returns plan info,
    messages used, members count, and limits.

    Requires service token (role=system).
    """
    from ..config.database import get_pool
    from ..repositories import plan_pricing_repo

    pool = await get_pool()

    # Get tenant info
    tenant = await pool.fetchrow(
        "SELECT id, plan, subscription_id FROM tenants WHERE id = $1",
        tenant_id,
    )
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

    plan_type = tenant["plan"] or "starter"

    # Get plan limits
    plan = await plan_pricing_repo.get_plan_by_type(plan_type)
    messages_limit = plan.get("max_messages_month") if plan else None
    members_limit = plan.get("max_members", 2) if plan else 2
    history_days = plan.get("history_days", 7) if plan else 7
    enabled_services = plan.get("enabled_services", ["reminder", "shopping"]) if plan else ["reminder", "shopping"]

    # Count messages this month
    messages_used = await pool.fetchval(
        """
        SELECT COUNT(*) FROM agent_interactions
        WHERE tenant_id = $1
          AND created_at >= date_trunc('month', NOW())
        """,
        tenant_id,
    ) or 0

    # Count active members
    members_count = await pool.fetchval(
        "SELECT COUNT(*) FROM users WHERE tenant_id = $1 AND is_active = true",
        tenant_id,
    ) or 0

    # Get subscription status
    subscription = await subscription_repo.get_subscription_by_tenant(tenant_id)
    sub_status = subscription["status"] if subscription else None

    return SubscriptionUsageResponse(
        tenant_id=tenant_id,
        plan=plan_type,
        messages_used=messages_used,
        messages_limit=messages_limit,
        members_count=members_count,
        members_limit=members_limit,
        history_days=history_days,
        enabled_services=enabled_services,
        subscription_status=sub_status,
        can_upgrade=plan_type in ("starter", "family"),
        can_downgrade=plan_type in ("family", "premium"),
    )


class BotUpgradeRequest(BaseModel):
    """Request from bot to generate upgrade checkout."""

    tenant_id: str
    plan_type: Literal["family", "premium"]


class BotCancelRequest(BaseModel):
    """Request from bot to cancel subscription."""

    tenant_id: str
    reason: str = "Sin motivo"


@router.post("/upgrade", response_model=SubscriptionCreateResponse)
async def create_upgrade_checkout(
    request: BotUpgradeRequest,
    _service_user: Annotated[CurrentUser, Depends(require_service_token)],
) -> SubscriptionCreateResponse:
    """
    Generate a checkout URL for plan upgrade (bot-facing).

    Requires service token (role=system).
    """
    service = get_subscription_service()

    try:
        # Use a placeholder email; LS will collect the real one
        result = await service.create_subscription(
            tenant_id=UUID(request.tenant_id),
            plan_type=request.plan_type,
            payer_email="upgrade@whatsapp.placeholder",
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except RuntimeError as e:
        logger.error("Payment provider error upgrading subscription", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Error al comunicarse con el proveedor de pagos. Intentá nuevamente.",
        )


@router.post("/cancel-by-tenant", response_model=SubscriptionCancelResponse)
async def cancel_subscription_by_tenant(
    request: BotCancelRequest,
    _service_user: Annotated[CurrentUser, Depends(require_service_token)],
) -> SubscriptionCancelResponse:
    """
    Cancel a subscription by tenant ID (bot-facing).

    Requires service token (role=system).
    """
    service = get_subscription_service()
    success, message = await service.cancel_subscription(
        tenant_id=UUID(request.tenant_id),
        reason=request.reason,
    )

    return SubscriptionCancelResponse(
        success=success,
        message=message,
    )


# =============================================================================
# Webhook endpoint (public, validated by HMAC signature)
# =============================================================================

webhook_router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@webhook_router.post("/lemonsqueezy", response_model=LemonSqueezyWebhookResponse)
async def lemonsqueezy_webhook(
    request: Request,
    x_signature: Annotated[str | None, Header(alias="x-signature")] = None,
) -> LemonSqueezyWebhookResponse:
    """Receive webhooks from Lemon Squeezy.

    The signature is validated using HMAC-SHA256 with the webhook secret.
    Requests without a valid signature are rejected.
    """
    if not x_signature:
        logger.warning("LS webhook missing x-signature header")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing webhook signature",
        )

    body = await request.body()

    ls_client = get_ls_client()
    if not ls_client.verify_webhook_signature(body, x_signature):
        logger.warning("Invalid LS webhook signature")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature",
        )

    # Parse JSON body
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload",
        )

    event_name = payload.get("meta", {}).get("event_name", "unknown")
    data = payload.get("data", {})
    meta = payload.get("meta", {})

    logger.info(f"Received LS webhook: event={event_name}, data_id={data.get('id')}")

    service = get_subscription_service()
    result = await service.process_ls_webhook(
        event_name=event_name,
        data=data,
        meta=meta,
    )

    return LemonSqueezyWebhookResponse(
        received=True,
        processed=result.get("processed", False),
        message=result.get("message"),
    )
