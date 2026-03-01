"""Reminder schemas for agent-facing reminder endpoints."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from .common import BaseSchema


class ReminderResponse(BaseSchema):
    """Reminder response."""

    id: UUID
    tenant_id: UUID
    user_id: UUID
    message: str
    trigger_at: datetime
    recurrence_rule: str | None = None
    status: str
    created_at: datetime


class AgentCreateReminderRequest(BaseModel):
    """Request schema for agent create reminder."""

    message: str = Field(..., min_length=1, max_length=500)
    trigger_date: str = Field(..., description="Date YYYY-MM-DD")
    trigger_time: str = Field(default="09:00", description="Time HH:MM")
    recurrence: str = Field(
        default="none",
        description="Recurrence: none, daily, weekly, monthly",
    )
    user_phone: str = Field(..., description="Phone to identify user")


class AgentListRemindersRequest(BaseModel):
    """Request schema for agent list reminders."""

    search: Optional[str] = Field(None, description="Search by text")
    user_phone: str = Field(..., description="Phone to identify user")


class AgentDeleteReminderRequest(BaseModel):
    """Request schema for agent delete reminder."""

    search_query: str = Field(..., min_length=1, description="Text to search")
    user_phone: str = Field(..., description="Phone to identify user")


class AgentReminderListResponse(BaseModel):
    """Response for listing reminders."""

    reminders: list[dict]
    count: int


class AgentReminderDeleteResponse(BaseModel):
    """Response for deleting a reminder."""

    deleted: bool
    message: str | None = None
