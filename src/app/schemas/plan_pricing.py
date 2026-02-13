"""Plan pricing schemas."""

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from .common import BaseSchema


# =============================================================================
# Types
# =============================================================================

PlanType = Literal["starter", "family", "premium"]


# =============================================================================
# Plan Pricing Schemas
# =============================================================================

class PlanPricingBase(BaseModel):
    """Base plan pricing fields."""

    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    price_monthly: Decimal = Field(..., ge=0)
    currency: str = Field(default="ARS", max_length=3)
    max_members: int = Field(..., ge=1)
    max_messages_month: int | None = Field(None, ge=1)  # None = unlimited
    history_days: int = Field(..., ge=1)
    features: list[str] = Field(default_factory=list)
    enabled_services: list[str] = Field(default_factory=list)


class PlanPricingUpdate(BaseModel):
    """Request to update plan pricing (admin only)."""

    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None
    price_monthly: Decimal | None = Field(None, ge=0)
    currency: str | None = Field(None, max_length=3)
    max_members: int | None = Field(None, ge=1)
    max_messages_month: int | None = None  # None = unlimited
    history_days: int | None = Field(None, ge=1)
    features: list[str] | None = None
    enabled_services: list[str] | None = None


class PlanPricingResponse(BaseSchema):
    """Plan pricing response schema (public)."""

    id: UUID
    plan_type: PlanType
    name: str
    description: str | None
    price_monthly: float
    currency: str
    max_members: int
    max_messages_month: int | None
    history_days: int
    features: list[str]
    enabled_services: list[str]
    active: bool

    @property
    def is_free(self) -> bool:
        """Check if plan is free."""
        return self.price_monthly == 0

    @property
    def has_unlimited_messages(self) -> bool:
        """Check if plan has unlimited messages."""
        return self.max_messages_month is None

    @property
    def has_unlimited_members(self) -> bool:
        """Check if plan effectively has unlimited members (999+)."""
        return self.max_members >= 999


class PlanPricingAdminResponse(PlanPricingResponse):
    """Plan pricing response with admin metadata."""

    updated_at: datetime
    updated_by: UUID | None


class PlanPricingListResponse(BaseModel):
    """List of plans."""

    items: list[PlanPricingResponse]


class PlanPricingAdminListResponse(BaseModel):
    """List of plans with admin metadata."""

    items: list[PlanPricingAdminResponse]


# =============================================================================
# Plan Comparison Schemas
# =============================================================================

class PlanComparisonResponse(BaseModel):
    """Compare current plan with another."""

    current_plan: PlanPricingResponse
    target_plan: PlanPricingResponse
    price_difference: float
    is_upgrade: bool
    features_gained: list[str]
    features_lost: list[str]
