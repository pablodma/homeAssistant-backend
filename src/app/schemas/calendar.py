"""Calendar schemas for events and Google Calendar integration."""

from datetime import date as date_type
from datetime import datetime
from datetime import time as time_type
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from .common import BaseSchema


class EventAction(str, Enum):
    """Calendar agent action types."""

    CREATE = "create"
    LIST = "list"
    UPDATE = "update"
    DELETE = "delete"


class SyncStatus(str, Enum):
    """Event sync status with Google Calendar."""

    LOCAL = "local"
    SYNCED = "synced"
    PENDING_SYNC = "pending_sync"
    SYNC_FAILED = "sync_failed"


class EventSource(str, Enum):
    """Event source."""

    APP = "app"
    GOOGLE = "google"


# =============================================================================
# Event Schemas
# =============================================================================


class EventBase(BaseModel):
    """Base event fields."""

    title: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(None, max_length=1000)
    location: str | None = Field(None, max_length=500)


class EventCreate(EventBase):
    """Create event request."""

    event_date: date_type = Field(..., description="Event date (YYYY-MM-DD)")
    start_time: Optional[time_type] = Field(None, description="Event start time (HH:MM)")
    duration_minutes: int = Field(default=60, ge=15, le=1440)
    timezone: str = Field(default="America/Argentina/Buenos_Aires")
    recurrence_rule: Optional[str] = Field(None, description="RRULE for recurring events")
    idempotency_key: Optional[str] = Field(None, max_length=100)

    @field_validator("event_date")
    @classmethod
    def validate_date_not_past(cls, v: date_type) -> date_type:
        """Warn if date is in the past (but allow it)."""
        return v


class EventUpdate(BaseModel):
    """Update event request."""

    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    location: Optional[str] = Field(None, max_length=500)
    event_date: Optional[date_type] = None
    start_time: Optional[time_type] = None
    duration_minutes: Optional[int] = Field(None, ge=15, le=1440)


class EventResponse(BaseSchema):
    """Event response."""

    id: UUID
    tenant_id: UUID
    title: str
    description: str | None
    location: str | None
    start_datetime: datetime
    end_datetime: datetime | None
    timezone: str
    recurrence_rule: str | None
    created_at: datetime
    updated_at: datetime
    created_by: UUID | None
    google_event_id: str | None = None
    google_calendar_id: str | None = None
    sync_status: SyncStatus = SyncStatus.LOCAL
    source: EventSource = EventSource.APP


class EventListResponse(BaseModel):
    """Event list response."""

    events: list[EventResponse]
    count: int
    date_range: "DateRange"


class DateRange(BaseModel):
    """Date range for event queries."""

    start_date: date_type
    end_date: date_type


# =============================================================================
# Google Calendar Connection Schemas
# =============================================================================


class GoogleCalendarConnectionStatus(BaseModel):
    """Google Calendar connection status response."""

    connected: bool
    calendar_id: str | None = None
    email: str | None = None
    auth_url: str | None = None
    expires_at: datetime | None = None
    message: str


class GoogleOAuthCallback(BaseModel):
    """OAuth callback request."""

    code: str
    state: str


class GoogleOAuthInitiate(BaseModel):
    """Initiate OAuth flow request."""

    user_phone: str
    redirect_url: str | None = None


class GoogleOAuthResponse(BaseModel):
    """OAuth initiation response."""

    auth_url: str
    state: str
    expires_at: datetime


# =============================================================================
# Agent Tool Schemas (for n8n HTTP Request)
# =============================================================================


class AgentCreateEventRequest(BaseModel):
    """Request schema for agent create_event action."""

    title: str = Field(..., min_length=1, max_length=200)
    event_date: date_type
    start_time: Optional[time_type] = None
    duration_minutes: int = Field(default=60, ge=15, le=1440)
    location: Optional[str] = None
    description: Optional[str] = None
    user_phone: Optional[str] = Field(None, description="Phone to identify user for Google sync")


class AgentUpdateEventRequest(BaseModel):
    """Request schema for agent update_event action."""

    search_query: Optional[str] = Field(None, description="Search term to find event")
    event_id: Optional[UUID] = Field(None, description="Direct event ID if known")
    title: Optional[str] = None
    event_date: Optional[date_type] = None
    start_time: Optional[time_type] = None
    duration_minutes: Optional[int] = None
    location: Optional[str] = None


class AgentDeleteEventRequest(BaseModel):
    """Request schema for agent delete_event action."""

    search_query: Optional[str] = Field(None, description="Search term to find event")
    event_id: Optional[UUID] = Field(None, description="Direct event ID if known")
    event_date: Optional[date_type] = Field(None, description="Filter by date")


class AgentListEventsRequest(BaseModel):
    """Request schema for agent list_events action."""

    event_date: Optional[date_type] = None
    start_date: Optional[date_type] = None
    end_date: Optional[date_type] = None
    search_query: Optional[str] = None
    include_google: bool = Field(default=True, description="Include Google Calendar events")


class AgentCheckAvailabilityRequest(BaseModel):
    """Request schema for checking availability."""

    event_date: date_type
    start_time: time_type
    duration_minutes: int = 60


class AgentAvailabilityResponse(BaseModel):
    """Availability check response."""

    available: bool
    conflicts: list[EventResponse] = []
    suggested_times: list[time_type] = []


# =============================================================================
# Event Detection Schemas (NLP)
# =============================================================================


class DetectedEvent(BaseModel):
    """Detected event from natural language."""

    title: str
    event_date: Optional[date_type] = None
    start_time: Optional[time_type] = None
    duration_minutes: Optional[int] = None
    location: Optional[str] = None
    is_recurring: bool = False
    recurrence_pattern: Optional[str] = None


class AgentDetectEventRequest(BaseModel):
    """Request to detect event from message."""

    message: str = Field(..., min_length=1, max_length=2000)
    user_phone: str
    context: list[dict] | None = Field(None, description="Conversation context")


class AgentDetectEventResponse(BaseModel):
    """Response from event detection."""

    detected: bool
    event_suggestion: DetectedEvent | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    needs_confirmation: bool = True
    missing_fields: list[str] = []
    message: str


# =============================================================================
# Duplicate Detection
# =============================================================================


class DuplicateCheckResponse(BaseModel):
    """Response when checking for duplicate events."""

    has_duplicate: bool
    existing_event: EventResponse | None = None
    similarity_score: float = 0.0
    message: str | None = None


class EventWithDuplicateCheck(BaseModel):
    """Event creation response with duplicate check."""

    event: EventResponse | None = None
    duplicate_warning: DuplicateCheckResponse | None = None
    created: bool


# Rebuild models for forward references
EventListResponse.model_rebuild()
