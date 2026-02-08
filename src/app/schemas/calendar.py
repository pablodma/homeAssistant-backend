"""Calendar schemas for events and Google Calendar integration."""

from datetime import date, datetime, time
from enum import Enum
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

    date: date = Field(..., description="Event date (YYYY-MM-DD)")
    time: time | None = Field(None, description="Event start time (HH:MM)")
    duration_minutes: int = Field(default=60, ge=15, le=1440)
    timezone: str = Field(default="America/Argentina/Buenos_Aires")
    recurrence_rule: str | None = Field(None, description="RRULE for recurring events")
    idempotency_key: str | None = Field(None, max_length=100)

    @field_validator("date")
    @classmethod
    def validate_date_not_past(cls, v: date) -> date:
        """Warn if date is in the past (but allow it)."""
        return v


class EventUpdate(BaseModel):
    """Update event request."""

    title: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = Field(None, max_length=1000)
    location: str | None = Field(None, max_length=500)
    date: date | None = None
    time: time | None = None
    duration_minutes: int | None = Field(None, ge=15, le=1440)


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

    start_date: date
    end_date: date


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
    date: date
    time: time | None = None
    duration_minutes: int = Field(default=60, ge=15, le=1440)
    location: str | None = None
    description: str | None = None
    user_phone: str | None = Field(None, description="Phone to identify user for Google sync")


class AgentUpdateEventRequest(BaseModel):
    """Request schema for agent update_event action."""

    search_query: str | None = Field(None, description="Search term to find event")
    event_id: UUID | None = Field(None, description="Direct event ID if known")
    title: str | None = None
    date: date | None = None
    time: time | None = None
    duration_minutes: int | None = None
    location: str | None = None


class AgentDeleteEventRequest(BaseModel):
    """Request schema for agent delete_event action."""

    search_query: str | None = Field(None, description="Search term to find event")
    event_id: UUID | None = Field(None, description="Direct event ID if known")
    date: date | None = Field(None, description="Filter by date")


class AgentListEventsRequest(BaseModel):
    """Request schema for agent list_events action."""

    date: date | None = None
    start_date: date | None = None
    end_date: date | None = None
    search_query: str | None = None
    include_google: bool = Field(default=True, description="Include Google Calendar events")


class AgentCheckAvailabilityRequest(BaseModel):
    """Request schema for checking availability."""

    date: date
    time: time
    duration_minutes: int = 60


class AgentAvailabilityResponse(BaseModel):
    """Availability check response."""

    available: bool
    conflicts: list[EventResponse] = []
    suggested_times: list[time] = []


# =============================================================================
# Event Detection Schemas (NLP)
# =============================================================================


class DetectedEvent(BaseModel):
    """Detected event from natural language."""

    title: str
    date: date | None = None
    time: time | None = None
    duration_minutes: int | None = None
    location: str | None = None
    is_recurring: bool = False
    recurrence_pattern: str | None = None


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
