"""Authentication schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr

from .common import BaseSchema


class GoogleAuthRequest(BaseModel):
    """Google OAuth callback request - code-based flow."""

    code: str


class GoogleIdTokenRequest(BaseModel):
    """Google OAuth request with ID token from frontend."""
    
    id_token: str


class TokenResponse(BaseModel):
    """JWT token response."""

    access_token: str
    token_type: str = "bearer"


class UserBase(BaseSchema):
    """Base user schema."""

    email: EmailStr | None = None
    display_name: str | None = None
    phone: str | None = None


class UserResponse(UserBase):
    """User response schema."""

    id: UUID
    tenant_id: UUID
    role: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class AuthResponse(BaseModel):
    """Authentication response with user and token."""

    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class CurrentUser(BaseModel):
    """Current authenticated user context."""

    id: UUID
    tenant_id: UUID
    email: str | None
    role: str
