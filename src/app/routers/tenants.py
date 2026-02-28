"""Tenant management endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from ..config.database import get_pool
from ..middleware.auth import (
    CurrentUser,
    check_tenant_access,
    get_current_user,
    require_admin,
)
from ..schemas.tenant import (
    InvitationResponse,
    TenantCreate,
    TenantDetailResponse,
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
    """Create a new tenant."""
    raise NotImplementedError("Tenant creation not yet implemented")


@router.get("/{tenant_id}", response_model=TenantDetailResponse)
async def get_tenant(
    tenant_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> TenantDetailResponse:
    """Get tenant details."""
    check_tenant_access(current_user, tenant_id)
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT t.id, t.name, t.home_name, t.plan, t.active,
                   t.timezone, t.language, t.currency, t.settings,
                   t.created_at, t.updated_at,
                   u.email AS owner_email, u.display_name AS owner_name
            FROM tenants t
            LEFT JOIN users u ON u.id = t.owner_user_id
            WHERE t.id = $1
            """,
            tenant_id,
        )
    if not row:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return TenantDetailResponse(
        id=row["id"],
        name=row["name"] or "",
        home_name=row["home_name"],
        plan=row["plan"] or "starter",
        active=row["active"],
        timezone=row["timezone"] or "America/Argentina/Buenos_Aires",
        language=row["language"] or "es",
        currency=row["currency"] or "ARS",
        settings=row["settings"] or {},
        owner_email=row["owner_email"],
        owner_name=row["owner_name"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


@router.put("/{tenant_id}/settings", response_model=TenantResponse)
async def update_tenant_settings(
    tenant_id: UUID,
    request: TenantUpdate,
    current_user: Annotated[CurrentUser, Depends(require_admin)],
) -> TenantResponse:
    """Update tenant settings. Requires admin or owner role."""
    check_tenant_access(current_user, tenant_id)
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
    check_tenant_access(current_user, tenant_id)
    raise NotImplementedError("Create invitation not yet implemented")
