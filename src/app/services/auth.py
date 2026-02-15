"""Authentication service for JWT token management and Google OAuth."""

from dataclasses import dataclass
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


@dataclass
class AuthResult:
    """Result of authentication with user and tenant info."""
    
    user_id: UUID
    tenant_id: UUID
    role: str
    onboarding_completed: bool
    is_new_user: bool = False


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


async def find_or_create_oauth_user(google_user: GoogleUserInfo) -> AuthResult:
    """
    Find existing user by email or create new one with a new tenant.
    
    Lookup order:
    1. Existing user with this email → return (could be owner or member added with email)
    2. No match → create new user + tenant (new owner starting onboarding)
    
    Also updates avatar_url, last_login_at, and email_verified on every login.
    
    Args:
        google_user: Google user info from ID token
        
    Returns:
        AuthResult with user, tenant, and onboarding status
    """
    pool = await get_pool()
    
    async with pool.acquire() as conn:
        # Try to find existing user by email (across all tenants)
        row = await conn.fetchrow(
            """
            SELECT u.id, u.tenant_id, u.role, t.onboarding_completed
            FROM users u
            JOIN tenants t ON u.tenant_id = t.id
            WHERE u.email = $1 AND u.is_active = true
            ORDER BY u.created_at ASC
            LIMIT 1
            """,
            google_user["email"],
        )
        
        if row:
            user_id = UUID(str(row["id"]))
            
            # Update profile info on every login
            await conn.execute(
                """
                UPDATE users SET 
                    avatar_url = $1,
                    display_name = COALESCE(display_name, $2),
                    email_verified = true,
                    auth_provider = 'google',
                    last_login_at = NOW()
                WHERE id = $3
                """,
                google_user.get("picture"),
                google_user.get("name"),
                user_id,
            )
            
            return AuthResult(
                user_id=user_id,
                tenant_id=UUID(str(row["tenant_id"])),
                role=row["role"],
                onboarding_completed=row["onboarding_completed"] or False,
                is_new_user=False,
            )
        
        # No existing user found → create new owner + tenant
        tenant_id = await conn.fetchval(
            """
            INSERT INTO tenants (name, onboarding_completed, settings)
            VALUES ($1, false, '{}'::jsonb)
            RETURNING id
            """,
            f"Tenant de {google_user.get('name') or google_user['email'].split('@')[0]}",
        )
        tenant_id = UUID(str(tenant_id))
        
        # Create new user as owner (no phone yet - added during onboarding)
        user_id = await conn.fetchval(
            """
            INSERT INTO users (
                tenant_id, email, display_name, role, auth_provider,
                avatar_url, email_verified, is_active, last_login_at
            )
            VALUES ($1, $2, $3, 'owner', 'google', $4, true, true, NOW())
            RETURNING id
            """,
            tenant_id,
            google_user["email"],
            google_user.get("name") or google_user["email"].split("@")[0],
            google_user.get("picture"),
        )
        user_id = UUID(str(user_id))
        
        # Set user as owner of tenant
        await conn.execute(
            "UPDATE tenants SET owner_user_id = $1 WHERE id = $2",
            user_id,
            tenant_id,
        )
        
        return AuthResult(
            user_id=user_id,
            tenant_id=tenant_id,
            role="owner",
            onboarding_completed=False,
            is_new_user=True,
        )


def create_access_token(
    user_id: str | UUID,
    tenant_id: str | UUID,
    role: str = "member",
    email: str | None = None,
    onboarding_completed: bool = True,
    expires_delta: timedelta | None = None,
) -> str:
    """
    Create a JWT access token.
    
    Args:
        user_id: User ID (or "system" for service tokens)
        tenant_id: Tenant ID
        role: User role (owner, admin, member, system)
        email: Optional email
        onboarding_completed: Whether user has completed onboarding
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
        "onboarding_completed": onboarding_completed,
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
