"""Tenant schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from .common import BaseSchema, TimestampMixin


class TenantSettings(BaseModel):
    """Tenant settings configuration."""

    timezone: str = "America/Argentina/Buenos_Aires"
    default_currency: str = "ARS"


class TenantCreate(BaseModel):
    """Create tenant request."""

    name: str = Field(..., min_length=1, max_length=200)


class TenantUpdate(BaseModel):
    """Update tenant request."""

    name: str | None = Field(None, min_length=1, max_length=200)
    settings: TenantSettings | None = None


class TenantResponse(BaseSchema, TimestampMixin):
    """Tenant response schema."""

    id: UUID
    name: str
    active: bool
    settings: dict


class TenantWithInvitation(TenantResponse):
    """Tenant response with invitation code."""

    invitation_code: str


class InvitationResponse(BaseModel):
    """Invitation response schema."""

    code: str
    expires_at: datetime
