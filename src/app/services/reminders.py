"""Reminders service for business logic."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status

from ..repositories import reminders as reminders_repo


async def agent_create_reminder(
    tenant_id: UUID,
    message: str,
    trigger_date: str,
    trigger_time: str,
    recurrence: str,
    user_phone: str,
) -> dict:
    """Create a reminder via agent."""
    user = await reminders_repo.get_user_by_phone(user_phone)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found for phone number",
        )

    trigger_at = datetime.strptime(f"{trigger_date} {trigger_time}", "%Y-%m-%d %H:%M")
    recurrence_rule = None if recurrence == "none" else recurrence

    row = await reminders_repo.create_reminder(
        tenant_id=tenant_id,
        user_id=user["id"],
        message=message,
        trigger_at=trigger_at,
        recurrence_rule=recurrence_rule,
    )

    return {
        "id": str(row["id"]),
        "message": message,
        "trigger_date": trigger_date,
        "trigger_time": trigger_time,
        "recurrence": recurrence,
    }


async def agent_list_reminders(
    tenant_id: UUID,
    user_phone: str,
    search: str | None = None,
) -> dict:
    """List pending reminders via agent."""
    user = await reminders_repo.get_user_by_phone(user_phone)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found for phone number",
        )

    rows = await reminders_repo.get_pending_reminders(
        tenant_id=tenant_id,
        user_id=user["id"],
        search=search,
    )

    reminders = [
        {
            "id": str(row["id"]),
            "message": row["message"],
            "trigger_date": row["trigger_at"].strftime("%Y-%m-%d") if row["trigger_at"] else None,
            "trigger_time": row["trigger_at"].strftime("%H:%M") if row["trigger_at"] else None,
            "recurrence": row["recurrence_rule"] or "none",
        }
        for row in rows
    ]

    return {"reminders": reminders, "count": len(reminders)}


async def agent_delete_reminder(
    tenant_id: UUID,
    search_query: str,
    user_phone: str,
) -> dict:
    """Delete a reminder by search text via agent."""
    user = await reminders_repo.get_user_by_phone(user_phone)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found for phone number",
        )

    row = await reminders_repo.delete_reminder_by_search(
        tenant_id=tenant_id,
        user_id=user["id"],
        search_query=search_query,
    )

    if row:
        return {"deleted": True, "message": row["message"]}
    return {"deleted": False, "message": None}


async def agent_update_reminder(
    tenant_id: UUID,
    search_query: str,
    user_phone: str,
    message: Optional[str] = None,
    trigger_date: Optional[str] = None,
    trigger_time: Optional[str] = None,
    recurrence: Optional[str] = None,
) -> dict:
    """Update a reminder by search text via agent."""
    user = await reminders_repo.get_user_by_phone(user_phone)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found for phone number",
        )

    trigger_at = None
    if trigger_date and trigger_time:
        trigger_at = datetime.strptime(f"{trigger_date} {trigger_time}", "%Y-%m-%d %H:%M")
    elif trigger_date:
        trigger_at = datetime.strptime(f"{trigger_date} 09:00", "%Y-%m-%d %H:%M")

    row = await reminders_repo.update_reminder_by_search(
        tenant_id=tenant_id,
        user_id=user["id"],
        search_query=search_query,
        message=message,
        trigger_at=trigger_at,
        recurrence_rule=recurrence,
    )

    if row:
        return {
            "updated": True,
            "id": str(row["id"]),
            "message": row["message"],
            "trigger_date": row["trigger_at"].strftime("%Y-%m-%d") if row.get("trigger_at") else None,
            "trigger_time": row["trigger_at"].strftime("%H:%M") if row.get("trigger_at") else None,
            "recurrence": row.get("recurrence_rule") or "none",
        }
    return {"updated": False, "message": None}


async def agent_complete_reminder(
    tenant_id: UUID,
    search_query: str,
    user_phone: str,
) -> dict:
    """Mark a reminder as completed by search text via agent."""
    user = await reminders_repo.get_user_by_phone(user_phone)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found for phone number",
        )

    row = await reminders_repo.complete_reminder_by_search(
        tenant_id=tenant_id,
        user_id=user["id"],
        search_query=search_query,
    )

    if row:
        return {"completed": True, "message": row["message"]}
    return {"completed": False, "message": None}
