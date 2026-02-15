"""Subscription management endpoints."""

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from ..config.lemonsqueezy import get_ls_client
from ..middleware.auth import CurrentUser, get_current_user
from ..repositories import subscription_repo
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
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


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
# Webhook endpoint (public, validated by HMAC signature)
# =============================================================================

webhook_router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@webhook_router.post("/lemonsqueezy", response_model=LemonSqueezyWebhookResponse)
async def lemonsqueezy_webhook(
    request: Request,
    x_signature: Annotated[str | None, Header(alias="x-signature")] = None,
) -> LemonSqueezyWebhookResponse:
    """
    Receive webhooks from Lemon Squeezy.

    This endpoint processes subscription and payment events.
    The signature is validated using HMAC-SHA256 with the webhook secret.
    """
    # Read raw body for signature verification
    body = await request.body()

    # Verify signature
    ls_client = get_ls_client()
    if x_signature:
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
