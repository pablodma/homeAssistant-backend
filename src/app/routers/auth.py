"""Authentication endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from ..middleware.auth import get_current_user
from ..schemas.auth import (
    CurrentUser,
    GoogleAuthRequest,
    GoogleIdTokenRequest,
    AuthResponse,
    UserResponse,
)
from ..services.auth import (
    create_access_token,
    verify_google_id_token,
    find_or_create_user,
    get_default_tenant,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/google/callback", response_model=AuthResponse)
async def google_callback(request: GoogleAuthRequest) -> AuthResponse:
    """
    Handle Google OAuth callback with authorization code.
    
    Exchange authorization code for tokens and create/update user.
    NOTE: This endpoint is for server-side OAuth flow.
    """
    # TODO: Implement server-side OAuth code exchange flow
    raise NotImplementedError("Google OAuth code flow not yet implemented")


@router.post("/google/token", response_model=AuthResponse)
async def google_token_auth(request: GoogleIdTokenRequest) -> AuthResponse:
    """
    Authenticate with Google ID token.
    
    This endpoint is for frontend OAuth flows where the frontend
    already has a Google ID token from NextAuth or similar.
    
    1. Validates Google ID token
    2. Finds or creates user in database
    3. Returns backend JWT token
    """
    # Verify Google ID token
    google_user = await verify_google_id_token(request.id_token)
    
    if not google_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google ID token",
        )
    
    if not google_user.get("email_verified"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email not verified with Google",
        )
    
    # Get default tenant (MVP: single tenant)
    tenant_id = await get_default_tenant()
    
    # Find or create user
    user_id, role = await find_or_create_user(google_user, tenant_id)
    
    # Create JWT token
    access_token = create_access_token(
        user_id=user_id,
        tenant_id=tenant_id,
        role=role,
        email=google_user["email"],
    )
    
    return AuthResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse(
            id=user_id,
            tenant_id=tenant_id,
            email=google_user["email"],
            display_name=google_user.get("name"),
            phone=None,
            role=role,
            created_at=None,  # Not fetching from DB for performance
            updated_at=None,
        ),
    )


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> UserResponse:
    """Get current authenticated user."""
    return UserResponse(
        id=current_user.id,
        tenant_id=current_user.tenant_id,
        email=current_user.email,
        display_name=None,  # Would fetch from DB in full implementation
        phone=None,
        role=current_user.role,
        created_at=None,
        updated_at=None,
    )
