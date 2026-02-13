"""Subscription schemas."""

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from .common import BaseSchema, TimestampMixin


# =============================================================================
# Enums and Types
# =============================================================================

PlanType = Literal["starter", "family", "premium"]
SubscriptionStatus = Literal["pending", "authorized", "paused", "cancelled", "ended"]
PaymentStatus = Literal["approved", "pending", "rejected", "refunded"]


# =============================================================================
# Subscription Schemas
# =============================================================================

class SubscriptionCreate(BaseModel):
    """Request to create a new subscription."""

    plan_type: Literal["family", "premium"]
    payer_email: EmailStr
    coupon_code: str | None = None


class SubscriptionResponse(BaseSchema, TimestampMixin):
    """Subscription response schema."""

    id: UUID
    tenant_id: UUID
    mp_preapproval_id: str | None = None
    plan_type: PlanType
    status: SubscriptionStatus
    current_period_start: datetime | None = None
    current_period_end: datetime | None = None
    cancelled_at: datetime | None = None


class SubscriptionCreateResponse(BaseModel):
    """Response after creating a subscription."""

    subscription_id: UUID
    checkout_url: str | None = None
    original_price: float
    discount_percent: int | None = None
    final_price: float
    plan_type: str


class SubscriptionStatusResponse(BaseModel):
    """Current subscription status for a tenant."""

    has_subscription: bool
    subscription: SubscriptionResponse | None = None
    current_plan: PlanType
    can_upgrade: bool
    can_downgrade: bool


# =============================================================================
# Subscription Payment Schemas
# =============================================================================

class SubscriptionPaymentResponse(BaseSchema):
    """Subscription payment record."""

    id: UUID
    subscription_id: UUID | None
    tenant_id: UUID
    mp_payment_id: str | None
    amount: float
    currency: str
    status: PaymentStatus
    paid_at: datetime | None
    created_at: datetime


class PaymentListResponse(BaseModel):
    """List of payments."""

    items: list[SubscriptionPaymentResponse]
    total: int


# =============================================================================
# Webhook Schemas
# =============================================================================

class WebhookData(BaseModel):
    """Data payload in webhook."""

    id: str


class WebhookPayload(BaseModel):
    """Mercado Pago webhook payload."""

    id: int | None = None
    live_mode: bool = False
    type: str
    date_created: str | None = None
    user_id: int | None = None
    api_version: str | None = None
    action: str
    data: WebhookData


class WebhookResponse(BaseModel):
    """Response to webhook."""

    received: bool = True
    processed: bool = False
    message: str | None = None


# =============================================================================
# Cancel/Pause Schemas
# =============================================================================

class SubscriptionCancelRequest(BaseModel):
    """Request to cancel subscription."""

    reason: str | None = None


class SubscriptionCancelResponse(BaseModel):
    """Response after cancelling."""

    success: bool
    message: str
    effective_date: datetime | None = None
