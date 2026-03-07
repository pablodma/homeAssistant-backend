"""Reminder endpoints for agent-facing operations."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from ..middleware.auth import get_current_user, validate_tenant_access
from ..schemas.auth import CurrentUser
from ..services import reminders as reminders_service

router = APIRouter(prefix="/tenants/{tenant_id}", tags=["Reminders"])


@router.post("/agent/reminders")
async def agent_create_reminder(
    tenant_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    _: Annotated[None, Depends(validate_tenant_access)],
    message: str = Query(..., description="What to remember"),
    trigger_date: str = Query(..., description="Date YYYY-MM-DD"),
    trigger_time: str = Query(default="09:00", description="Time HH:MM"),
    recurrence: str = Query(default="none", description="none, daily, weekly, monthly"),
    user_phone: str = Query(..., description="User phone"),
) -> dict:
    """Create a reminder (agent-facing)."""
    return await reminders_service.agent_create_reminder(
        tenant_id=tenant_id,
        message=message,
        trigger_date=trigger_date,
        trigger_time=trigger_time,
        recurrence=recurrence,
        user_phone=user_phone,
    )


@router.get("/agent/reminders")
async def agent_list_reminders(
    tenant_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    _: Annotated[None, Depends(validate_tenant_access)],
    user_phone: str = Query(..., description="User phone"),
    search: str | None = Query(None, description="Search by text"),
) -> dict:
    """List pending reminders (agent-facing)."""
    return await reminders_service.agent_list_reminders(
        tenant_id=tenant_id,
        user_phone=user_phone,
        search=search,
    )


@router.delete("/agent/reminders/search")
async def agent_delete_reminder(
    tenant_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    _: Annotated[None, Depends(validate_tenant_access)],
    search_query: str = Query(..., description="Text to search"),
    user_phone: str = Query(..., description="User phone"),
) -> dict:
    """Delete a reminder by search text (agent-facing)."""
    return await reminders_service.agent_delete_reminder(
        tenant_id=tenant_id,
        search_query=search_query,
        user_phone=user_phone,
    )


@router.put("/agent/reminders/search")
async def agent_update_reminder(
    tenant_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    _: Annotated[None, Depends(validate_tenant_access)],
    search_query: str = Query(..., description="Text to find the reminder"),
    user_phone: str = Query(..., description="User phone"),
    message: str | None = Query(None, description="New message"),
    trigger_date: str | None = Query(None, description="New date YYYY-MM-DD"),
    trigger_time: str | None = Query(None, description="New time HH:MM"),
    recurrence: str | None = Query(None, description="New recurrence: none, daily, weekly, monthly"),
) -> dict:
    """Update a reminder by search text (agent-facing)."""
    return await reminders_service.agent_update_reminder(
        tenant_id=tenant_id,
        search_query=search_query,
        user_phone=user_phone,
        message=message,
        trigger_date=trigger_date,
        trigger_time=trigger_time,
        recurrence=recurrence,
    )


@router.post("/agent/reminders/complete")
async def agent_complete_reminder(
    tenant_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    _: Annotated[None, Depends(validate_tenant_access)],
    search_query: str = Query(..., description="Text to find the reminder"),
    user_phone: str = Query(..., description="User phone"),
) -> dict:
    """Mark a reminder as completed (agent-facing)."""
    return await reminders_service.agent_complete_reminder(
        tenant_id=tenant_id,
        search_query=search_query,
        user_phone=user_phone,
    )
