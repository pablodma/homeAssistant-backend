"""Authentication endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends

from ..middleware.auth import get_current_user
from ..schemas.auth import CurrentUser, GoogleAuthRequest, AuthResponse, UserResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/google/callback", response_model=AuthResponse)
async def google_callback(request: GoogleAuthRequest) -> AuthResponse:
    """
    Handle Google OAuth callback.
    
    Exchange authorization code for tokens and create/update user.
    """
    # TODO: Implement Google OAuth flow
    # 1. Exchange code for tokens with Google
    # 2. Get user info from Google
    # 3. Find or create user in database
    # 4. Generate JWT token
    raise NotImplementedError("Google OAuth not yet implemented")


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> UserResponse:
    """Get current authenticated user."""
    # TODO: Fetch full user from database
    raise NotImplementedError("Get current user not yet implemented")
