"""Unified access policy endpoints for web and bot."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from ..middleware.auth import CurrentUser, get_current_user, require_service_token
from ..schemas.access import AccessStatusResponse
from ..services.access_policy import get_access_policy_service

router = APIRouter(prefix="/access", tags=["Access"])


@router.get("/status", response_model=AccessStatusResponse)
async def get_access_status(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> AccessStatusResponse:
    """Get access status for the authenticated web user."""
    service = get_access_policy_service()
    return await service.get_access_status_for_user(current_user.id)


@router.get("/status-by-phone", response_model=AccessStatusResponse)
async def get_access_status_by_phone(
    phone: str = Query(..., description="Phone number in E.164 format"),
    _service_user: Annotated[CurrentUser, Depends(require_service_token)] = None,
) -> AccessStatusResponse:
    """Get access status for bot traffic using a phone number."""
    service = get_access_policy_service()
    return await service.get_access_status_by_phone(phone)
