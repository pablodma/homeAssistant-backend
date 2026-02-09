"""Onboarding schemas for tenant creation and phone registration."""

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
    
    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        """Validate phone is in E.164 format."""
        import re
        if not re.match(r"^\+\d{10,15}$", v):
            raise ValueError("Phone must be in E.164 format (e.g., +5491112345678)")
        return v


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


class PhoneTenantMapping(BaseSchema):
    """Phone to tenant mapping response."""
    
    phone: str
    tenant_id: UUID
    user_id: UUID | None = None
    display_name: str | None = None
    is_primary: bool = False
    verified_at: datetime | None = None


class PhoneLookupResponse(BaseModel):
    """Response for phone lookup (used by bot)."""
    
    found: bool
    tenant_id: UUID | None = None
    user_name: str | None = None
    home_name: str | None = None


class RegisterPhoneRequest(BaseModel):
    """Request to register a phone number to a tenant."""
    
    phone: str = Field(..., description="Phone number in E.164 format")
    display_name: str = Field(..., min_length=1, max_length=100)
    is_primary: bool = Field(default=False)
    
    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        """Validate phone is in E.164 format."""
        import re
        if not re.match(r"^\+\d{10,15}$", v):
            raise ValueError("Phone must be in E.164 format (e.g., +5491112345678)")
        return v
