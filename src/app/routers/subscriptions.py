"""Subscription management endpoints."""

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from ..middleware.auth import CurrentUser, get_current_user
from ..repositories import subscription_repo
from ..schemas.subscription import (
    PaymentListResponse,
    SubscriptionCancelRequest,
    SubscriptionCancelResponse,
    SubscriptionCreate,
    SubscriptionCreateResponse,
    SubscriptionPaymentResponse,
    SubscriptionResponse,
    SubscriptionStatusResponse,
    WebhookPayload,
    WebhookResponse,
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
    3. Creates a preapproval in Mercado Pago
    4. Returns the checkout URL for payment
    """
    if not current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User must belong to a tenant to subscribe"
        )

    service = get_subscription_service()

    try:
        result = await service.create_subscription(
            tenant_id=current_user.tenant_id,
            plan_type=request.plan_type,
            payer_email=request.payer_email,
            coupon_code=request.coupon_code,
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(e)
        )


@router.get("/me", response_model=SubscriptionStatusResponse)
async def get_my_subscription(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> SubscriptionStatusResponse:
    """Get subscription status for the current tenant."""
    if not current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User must belong to a tenant"
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
            detail="User must belong to a tenant"
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
            detail="User must belong to a tenant"
        )

    service = get_subscription_service()
    success, message = await service.pause_subscription(
        tenant_id=current_user.tenant_id,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )

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
            detail="User must belong to a tenant"
        )

    payments = await subscription_repo.get_payments_by_tenant(
        tenant_id=current_user.tenant_id,
        limit=limit,
        offset=offset,
    )

    return PaymentListResponse(
        items=[SubscriptionPaymentResponse(**p) for p in payments],
        total=len(payments),  # TODO: Get actual total count
    )


@router.post("/sync", response_model=SubscriptionResponse | None)
async def sync_subscription(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> SubscriptionResponse | None:
    """
    Sync subscription status with Mercado Pago.
    
    Call this if you suspect local data is out of sync.
    """
    if not current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User must belong to a tenant"
        )

    subscription = await subscription_repo.get_subscription_by_tenant(current_user.tenant_id)
    if not subscription:
        return None

    service = get_subscription_service()
    updated = await service.sync_subscription_status(subscription["id"])
    return SubscriptionResponse(**updated) if updated else None


# =============================================================================
# Webhook endpoint (public, validated by signature)
# =============================================================================

webhook_router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@webhook_router.post("/mercadopago", response_model=WebhookResponse)
async def mercadopago_webhook(
    payload: WebhookPayload,
    request: Request,
    x_signature: Annotated[str | None, Header()] = None,
    x_request_id: Annotated[str | None, Header()] = None,
) -> WebhookResponse:
    """
    Receive webhooks from Mercado Pago.
    
    This endpoint processes payment and subscription events.
    The signature is validated using the webhook secret.
    """
    logger.info(f"Received MP webhook: action={payload.action}, type={payload.type}")

    service = get_subscription_service()
    return await service.process_webhook(
        payload=payload,
        x_signature=x_signature,
        x_request_id=x_request_id,
    )
