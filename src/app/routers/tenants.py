"""Tenant management endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from ..middleware.auth import (
    CurrentUser,
    get_current_user,
    require_admin,
    validate_tenant_access,
)
from ..schemas.tenant import (
    InvitationResponse,
    TenantCreate,
    TenantResponse,
    TenantUpdate,
    TenantWithInvitation,
)

router = APIRouter(prefix="/tenants", tags=["Tenants"])


@router.post("", response_model=TenantWithInvitation, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    request: TenantCreate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> TenantWithInvitation:
    """
    Create a new tenant.
    
    The authenticated user becomes the owner of the new tenant.
    """
    # TODO: Implement tenant creation
    # 1. Create tenant in database
    # 2. Create user as owner of tenant
    # 3. Generate invitation code
    raise NotImplementedError("Tenant creation not yet implemented")


@router.get("/{tenant_id}", response_model=TenantResponse)
async def get_tenant(
    tenant_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> TenantResponse:
    """Get tenant details."""
    validate_tenant_access(current_user.tenant_id, tenant_id)
    
    # TODO: Fetch tenant from database
    raise NotImplementedError("Get tenant not yet implemented")


@router.put("/{tenant_id}/settings", response_model=TenantResponse)
async def update_tenant_settings(
    tenant_id: UUID,
    request: TenantUpdate,
    current_user: Annotated[CurrentUser, Depends(require_admin)],
) -> TenantResponse:
    """Update tenant settings. Requires admin or owner role."""
    validate_tenant_access(current_user.tenant_id, tenant_id)
    
    # TODO: Update tenant in database
    raise NotImplementedError("Update tenant not yet implemented")


@router.post(
    "/{tenant_id}/invitations",
    response_model=InvitationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_invitation(
    tenant_id: UUID,
    current_user: Annotated[CurrentUser, Depends(require_admin)],
) -> InvitationResponse:
    """Create invitation code. Requires admin or owner role."""
    validate_tenant_access(current_user.tenant_id, tenant_id)
    
    # TODO: Create invitation in database
    raise NotImplementedError("Create invitation not yet implemented")
