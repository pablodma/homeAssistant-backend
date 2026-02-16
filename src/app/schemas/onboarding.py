"""Onboarding schemas for tenant creation and member management."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from .common import BaseSchema


class PhoneMember(BaseModel):
    """A household member with their phone number."""
    
    phone: str = Field(..., description="Phone number in E.164 format (+5491112345678)")
    name: str = Field(..., min_length=1, max_length=100, description="Member display name")
    role: Literal["admin", "member"] = Field(default="member", description="Member role")
    email: str | None = Field(default=None, description="Optional email for web login")
    
    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        """Validate phone is in E.164 format."""
        import re
        if not re.match(r"^\+\d{10,15}$", v):
            raise ValueError("Phone must be in E.164 format (e.g., +5491112345678)")
        return v

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str | None) -> str | None:
        """Validate email format if provided."""
        if v is None or v == "":
            return None
        import re
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", v):
            raise ValueError("Invalid email format")
        return v.lower().strip()


class OnboardingRequest(BaseModel):
    """Request to complete onboarding and create tenant."""
    
    home_name: str = Field(..., min_length=2, max_length=100, description="Household name")
    plan: Literal["starter", "family", "premium"] = Field(default="starter")
    members: list[PhoneMember] = Field(..., min_length=1, description="Household members")
    timezone: str = Field(default="America/Argentina/Buenos_Aires")
    language: str = Field(default="es-AR")
    currency: str = Field(default="ARS")
    
    @field_validator("members")
    @classmethod
    def validate_members(cls, v: list[PhoneMember]) -> list[PhoneMember]:
        """Ensure at least one admin member."""
        if not any(m.role == "admin" for m in v):
            raise ValueError("At least one member must have admin role")
        return v


class OnboardingResponse(BaseSchema):
    """Response after successful onboarding."""
    
    tenant_id: UUID
    home_name: str
    plan: str
    members_count: int
    onboarding_completed: bool = True
    message: str = "Onboarding completado exitosamente"


class OnboardingStatusResponse(BaseModel):
    """Response for checking onboarding status."""
    
    onboarding_completed: bool
    tenant_id: UUID | None = None
    home_name: str | None = None


class MemberResponse(BaseSchema):
    """A member of a tenant/account."""
    
    id: UUID
    phone: str | None = None
    email: str | None = None
    display_name: str | None = None
    role: str = "member"
    phone_verified: bool = False
    email_verified: bool = False
    avatar_url: str | None = None
    is_active: bool = True
    created_at: datetime | None = None


class PhoneLookupResponse(BaseModel):
    """Response for phone lookup (used by bot)."""
    
    found: bool
    tenant_id: UUID | None = None
    user_name: str | None = None
    home_name: str | None = None


class AddMemberRequest(BaseModel):
    """Request to add a member to a tenant."""
    
    phone: str = Field(..., description="Phone number in E.164 format")
    display_name: str = Field(..., min_length=1, max_length=100)
    role: Literal["admin", "member"] = Field(default="member")
    email: str | None = Field(default=None, description="Optional email for web login")
    
    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        """Validate phone is in E.164 format."""
        import re
        if not re.match(r"^\+\d{10,15}$", v):
            raise ValueError("Phone must be in E.164 format (e.g., +5491112345678)")
        return v


# =============================================================================
# WhatsApp Onboarding Schemas (used by bot via service token)
# =============================================================================


class WhatsAppOnboardingRequest(BaseModel):
    """Request to create a tenant from WhatsApp onboarding (Starter plan)."""
    
    phone: str = Field(..., description="Phone number in E.164 format")
    display_name: str = Field(..., min_length=1, max_length=100)
    home_name: str = Field(..., min_length=2, max_length=100)
    plan: Literal["starter"] = Field(default="starter")
    timezone: str = Field(default="America/Argentina/Buenos_Aires")
    language: str = Field(default="es-AR")
    currency: str = Field(default="ARS")

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        """Validate phone format."""
        import re
        if not re.match(r"^\+\d{10,15}$", v):
            raise ValueError("Phone must be in E.164 format")
        return v


class WhatsAppOnboardingResponse(BaseModel):
    """Response after WhatsApp onboarding."""
    
    tenant_id: UUID
    home_name: str
    plan: str
    message: str = "Cuenta creada exitosamente"


class WhatsAppPendingRequest(BaseModel):
    """Request to create a pending registration for paid plans."""
    
    phone: str = Field(..., description="Phone number in E.164 format")
    display_name: str = Field(..., min_length=1, max_length=100)
    home_name: str = Field(..., min_length=2, max_length=100)
    plan_type: Literal["family", "premium"]
    coupon_code: str | None = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        """Validate phone format."""
        import re
        if not re.match(r"^\+\d{10,15}$", v):
            raise ValueError("Phone must be in E.164 format")
        return v


class WhatsAppPendingResponse(BaseModel):
    """Response after creating a pending registration."""
    
    pending_id: UUID
    checkout_url: str | None = None
    plan_type: str
    message: str = "Registro pendiente de pago"


class BotInviteMemberRequest(BaseModel):
    """Request to invite a member via bot (service token)."""

    phone: str = Field(..., description="Phone number in E.164 format")

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        """Validate phone format."""
        import re
        if not re.match(r"^\+\d{10,15}$", v):
            raise ValueError("Phone must be in E.164 format (e.g., +5491112345678)")
        return v


class BotInviteMemberResponse(BaseModel):
    """Response after bot invites a member."""

    success: bool
    member_id: UUID
    phone: str
    message: str = "Miembro agregado al hogar"


class SubscriptionUsageResponse(BaseModel):
    """Usage stats for a tenant's subscription."""
    
    tenant_id: UUID
    plan: str
    messages_used: int
    messages_limit: int | None = None
    members_count: int
    members_limit: int
    history_days: int
    enabled_services: list[str]
    subscription_status: str | None = None
    can_upgrade: bool
    can_downgrade: bool
