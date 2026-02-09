"""Authentication middleware and dependencies."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Path, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from ..config import get_settings
from ..schemas.auth import CurrentUser

security = HTTPBearer()


def _parse_user_id(user_id_str: str) -> UUID:
    """Parse user ID, handling service tokens."""
    # Service tokens have IDs like "service-n8n"
    if user_id_str.startswith("service-"):
        # Generate a deterministic UUID for service accounts
        import hashlib
        hash_bytes = hashlib.md5(user_id_str.encode()).digest()
        return UUID(bytes=hash_bytes)
    return UUID(user_id_str)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
) -> CurrentUser:
    """Extract and validate current user from JWT token."""
    settings = get_settings()

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        user_id: str | None = payload.get("sub")
        tenant_id: str | None = payload.get("tenant_id")

        if user_id is None or tenant_id is None:
            raise credentials_exception

        return CurrentUser(
            id=_parse_user_id(user_id),
            tenant_id=UUID(tenant_id),
            email=payload.get("email"),
            role=payload.get("role", "member"),
            onboarding_completed=payload.get("onboarding_completed", True),
        )
    except JWTError:
        raise credentials_exception


async def require_admin(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> CurrentUser:
    """Require admin or owner role."""
    if current_user.role not in ("admin", "owner"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or owner role required",
        )
    return current_user


async def require_owner(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> CurrentUser:
    """Require owner role."""
    if current_user.role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner role required",
        )
    return current_user


security_optional = HTTPBearer(auto_error=False)


async def get_current_user_optional(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security_optional)],
) -> CurrentUser | None:
    """
    Extract user from JWT token if present, return None otherwise.
    
    Use this for endpoints that work with or without authentication,
    such as internal admin endpoints protected by other layers (NextAuth).
    """
    if credentials is None:
        return None
    
    settings = get_settings()
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        user_id: str | None = payload.get("sub")
        tenant_id: str | None = payload.get("tenant_id")

        if user_id is None or tenant_id is None:
            return None

        return CurrentUser(
            id=_parse_user_id(user_id),
            tenant_id=UUID(tenant_id),
            email=payload.get("email"),
            role=payload.get("role", "member"),
            onboarding_completed=payload.get("onboarding_completed", True),
        )
    except JWTError:
        return None


async def validate_tenant_access(
    tenant_id: Annotated[UUID, Path(description="Tenant ID")],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> None:
    """Validate user has access to the requested tenant."""
    # System role (service tokens) can access any tenant they're issued for
    if current_user.role == "system":
        if current_user.tenant_id != tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Service token not authorized for this tenant",
            )
        return
    
    if current_user.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this tenant",
        )
