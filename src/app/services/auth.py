"""Authentication service for JWT token management and Google OAuth."""

from datetime import datetime, timedelta, timezone
from typing import TypedDict
from uuid import UUID

import httpx
from jose import jwt

from ..config import get_settings
from ..config.database import get_pool


class GoogleUserInfo(TypedDict):
    """Google user info from ID token."""
    
    sub: str  # Google user ID
    email: str
    email_verified: bool
    name: str | None
    picture: str | None


async def verify_google_id_token(id_token: str) -> GoogleUserInfo | None:
    """
    Verify Google ID token and extract user info.
    
    Uses Google's tokeninfo endpoint for validation.
    
    Args:
        id_token: The Google ID token from frontend
        
    Returns:
        User info dict if valid, None if invalid
    """
    settings = get_settings()
    
    async with httpx.AsyncClient() as client:
        # Validate token with Google
        response = await client.get(
            f"https://oauth2.googleapis.com/tokeninfo?id_token={id_token}"
        )
        
        if response.status_code != 200:
            return None
            
        data = response.json()
        
        # Verify the token was issued for our app
        if data.get("aud") != settings.google_client_id:
            return None
            
        return GoogleUserInfo(
            sub=data["sub"],
            email=data["email"],
            email_verified=data.get("email_verified", "false") == "true",
            name=data.get("name"),
            picture=data.get("picture"),
        )


async def find_or_create_user(
    google_user: GoogleUserInfo,
    tenant_id: UUID,
) -> tuple[UUID, str]:
    """
    Find existing user by email or create new one.
    
    Args:
        google_user: Google user info from ID token
        tenant_id: Tenant to associate user with
        
    Returns:
        Tuple of (user_id, role)
    """
    pool = await get_pool()
    
    async with pool.acquire() as conn:
        # Try to find existing user by email
        row = await conn.fetchrow(
            """
            SELECT id, role FROM users 
            WHERE email = $1 AND tenant_id = $2
            """,
            google_user["email"],
            tenant_id,
        )
        
        if row:
            return UUID(str(row["id"])), row["role"]
        
        # Create new user
        # Use email as phone placeholder for OAuth users (phone is required in schema)
        user_id = await conn.fetchval(
            """
            INSERT INTO users (tenant_id, email, phone, display_name, role)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id
            """,
            tenant_id,
            google_user["email"],
            f"oauth:{google_user['email']}",  # Placeholder phone for OAuth users
            google_user.get("name") or google_user["email"].split("@")[0],
            "member",  # Default role for new users
        )
        
        return UUID(str(user_id)), "member"


async def get_default_tenant() -> UUID:
    """
    Get the default tenant ID.
    
    For MVP, we use a hardcoded default tenant.
    In production, this would be based on domain, invitation, etc.
    
    Returns:
        Default tenant UUID
    """
    # Default tenant for MVP
    return UUID("00000000-0000-0000-0000-000000000001")


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
