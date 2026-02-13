"""Coupon schemas."""

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from .common import BaseSchema


# =============================================================================
# Types
# =============================================================================

ApplicablePlan = Literal["family", "premium"]


# =============================================================================
# Coupon Schemas
# =============================================================================

class CouponBase(BaseModel):
    """Base coupon fields."""

    code: str = Field(..., min_length=3, max_length=50)
    description: str | None = None
    discount_percent: int = Field(..., ge=1, le=100)
    applicable_plans: list[ApplicablePlan]

    @field_validator("code")
    @classmethod
    def uppercase_code(cls, v: str) -> str:
        """Convert code to uppercase."""
        return v.upper().strip()

    @field_validator("applicable_plans")
    @classmethod
    def validate_plans(cls, v: list[ApplicablePlan]) -> list[ApplicablePlan]:
        """Ensure at least one plan is selected."""
        if not v:
            raise ValueError("At least one plan must be selected")
        return list(set(v))  # Remove duplicates


class CouponCreate(CouponBase):
    """Request to create a new coupon."""

    valid_from: datetime | None = None  # Default: now
    valid_until: datetime | None = None  # None = no expiration
    max_redemptions: int | None = Field(None, ge=1)  # None = unlimited
    active: bool = True


class CouponUpdate(BaseModel):
    """Request to update a coupon."""

    description: str | None = None
    valid_until: datetime | None = None
    max_redemptions: int | None = Field(None, ge=1)
    active: bool | None = None


class CouponResponse(BaseSchema):
    """Coupon response schema."""

    id: UUID
    code: str
    description: str | None
    discount_percent: int
    applicable_plans: list[str]
    valid_from: datetime
    valid_until: datetime | None
    max_redemptions: int | None
    current_redemptions: int
    active: bool
    created_at: datetime
    created_by: UUID | None

    @property
    def is_expired(self) -> bool:
        """Check if coupon is expired."""
        if self.valid_until is None:
            return False
        return datetime.now(self.valid_until.tzinfo) > self.valid_until

    @property
    def is_exhausted(self) -> bool:
        """Check if coupon has reached max redemptions."""
        if self.max_redemptions is None:
            return False
        return self.current_redemptions >= self.max_redemptions

    @property
    def is_usable(self) -> bool:
        """Check if coupon can be used."""
        return self.active and not self.is_expired and not self.is_exhausted


class CouponListResponse(BaseModel):
    """List of coupons."""

    items: list[CouponResponse]
    total: int


# =============================================================================
# Coupon Validation Schemas
# =============================================================================

class CouponValidateRequest(BaseModel):
    """Request to validate a coupon code."""

    code: str = Field(..., min_length=1)
    plan_type: Literal["family", "premium"]

    @field_validator("code")
    @classmethod
    def uppercase_code(cls, v: str) -> str:
        """Convert code to uppercase."""
        return v.upper().strip()


class CouponValidateResponse(BaseModel):
    """Response from coupon validation."""

    valid: bool
    discount_percent: int | None = None
    description: str | None = None
    error: str | None = None


# =============================================================================
# Coupon Redemption Schemas
# =============================================================================

class CouponRedemptionResponse(BaseSchema):
    """Coupon redemption record."""

    id: UUID
    coupon_id: UUID
    tenant_id: UUID
    subscription_id: UUID | None
    discount_applied: float
    original_price: float
    final_price: float
    redeemed_at: datetime


class CouponStatsResponse(BaseModel):
    """Coupon statistics."""

    coupon_id: UUID
    code: str
    total_redemptions: int
    total_discount_given: float
    recent_redemptions: list[CouponRedemptionResponse]
