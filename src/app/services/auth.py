"""Authentication service for JWT token management."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from jose import jwt

from ..config import get_settings


def create_access_token(
    user_id: str | UUID,
    tenant_id: str | UUID,
    role: str = "member",
    email: str | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """
    Create a JWT access token.
    
    Args:
        user_id: User ID (or "system" for service tokens)
        tenant_id: Tenant ID
        role: User role (owner, admin, member, system)
        email: Optional email
        expires_delta: Optional custom expiration time
    
    Returns:
        Encoded JWT token
    """
    settings = get_settings()
    
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.jwt_expire_minutes)
    
    now = datetime.now(timezone.utc)
    expire = now + expires_delta
    
    payload = {
        "sub": str(user_id),
        "tenant_id": str(tenant_id),
        "role": role,
        "exp": expire,
        "iat": now,
    }
    
    if email:
        payload["email"] = email
    
    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def create_service_token(
    tenant_id: str | UUID,
    service_name: str = "n8n",
    expires_days: int = 365,
) -> str:
    """
    Create a long-lived service token for external integrations.
    
    Args:
        tenant_id: Tenant ID the service will access
        service_name: Name of the service (e.g., "n8n", "whatsapp")
        expires_days: Token validity in days (default 1 year)
    
    Returns:
        Encoded JWT token
    """
    return create_access_token(
        user_id=f"service-{service_name}",
        tenant_id=tenant_id,
        role="system",
        expires_delta=timedelta(days=expires_days),
    )


def decode_token(token: str) -> dict:
    """
    Decode and validate a JWT token.
    
    Args:
        token: The JWT token to decode
    
    Returns:
        Decoded payload
    
    Raises:
        JWTError: If token is invalid or expired
    """
    settings = get_settings()
    return jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )
