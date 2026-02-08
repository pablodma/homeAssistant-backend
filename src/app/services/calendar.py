"""Calendar service for business logic."""

import secrets
from datetime import date, datetime, time, timedelta
from uuid import UUID

from fastapi import HTTPException, status

from ..config.settings import get_settings
from ..repositories import calendar_repo
from ..schemas.calendar import (
    AgentAvailabilityResponse,
    AgentCreateEventRequest,
    AgentDetectEventRequest,
    AgentDetectEventResponse,
    AgentListEventsRequest,
    DateRange,
    DetectedEvent,
    DuplicateCheckResponse,
    EventCreate,
    EventListResponse,
    EventResponse,
    EventSource,
    EventUpdate,
    EventWithDuplicateCheck,
    GoogleCalendarConnectionStatus,
    GoogleOAuthResponse,
    SyncStatus,
)
from . import google_calendar as gcal_service
from .event_detector import detect_event_in_message

settings = get_settings()


# =============================================================================
# Event CRUD Operations
# =============================================================================


async def create_event(
    tenant_id: UUID,
    data: EventCreate,
    created_by: UUID | None = None,
    sync_to_google: bool = True,
    user_id_for_sync: UUID | None = None,
) -> EventWithDuplicateCheck:
    """Create a new event with duplicate detection and optional Google sync."""
    if data.start_time:
        start_dt = datetime.combine(data.event_date, data.start_time)
    else:
        start_dt = datetime.combine(data.event_date, time(9, 0))

    end_dt = start_dt + timedelta(minutes=data.duration_minutes)

    duplicate = await check_for_duplicate(tenant_id, start_dt, data.title)
    if duplicate.has_duplicate:
        return EventWithDuplicateCheck(
            event=None,
            duplicate_warning=duplicate,
            created=False,
        )

    record = await calendar_repo.create_event(
        tenant_id=tenant_id,
        title=data.title,
        start_datetime=start_dt,
        end_datetime=end_dt,
        description=data.description,
        location=data.location,
        timezone=data.timezone,
        recurrence_rule=data.recurrence_rule,
        created_by=created_by,
        idempotency_key=data.idempotency_key,
        sync_status="pending_sync" if sync_to_google else "local",
        source="app",
    )

    event = _record_to_event_response(record)

    if sync_to_google and user_id_for_sync:
        try:
            google_event = await gcal_service.create_event(
                user_id=user_id_for_sync,
                title=data.title,
                start_datetime=start_dt,
                end_datetime=end_dt,
                description=data.description,
                location=data.location,
                timezone=data.timezone,
            )

            await calendar_repo.update_event(
                tenant_id=tenant_id,
                event_id=record["id"],
                google_event_id=google_event["id"],
                sync_status="synced",
                last_synced_at=datetime.utcnow(),
            )

            event.google_event_id = google_event["id"]
            event.sync_status = SyncStatus.SYNCED

        except gcal_service.GoogleCalendarError:
            await calendar_repo.update_event(
                tenant_id=tenant_id,
                event_id=record["id"],
                sync_status="pending_sync",
            )
            event.sync_status = SyncStatus.PENDING_SYNC

    return EventWithDuplicateCheck(
        event=event,
        duplicate_warning=None,
        created=True,
    )


async def get_event(tenant_id: UUID, event_id: UUID) -> EventResponse:
    """Get a single event by ID."""
    record = await calendar_repo.get_event_by_id(tenant_id, event_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )
    return _record_to_event_response(record)


async def list_events(
    tenant_id: UUID,
    start_date: date | None = None,
    end_date: date | None = None,
    search_query: str | None = None,
    include_google: bool = True,
    user_id_for_google: UUID | None = None,
) -> EventListResponse:
    """List events with optional Google Calendar integration."""
    if not start_date:
        start_date = date.today()
    if not end_date:
        end_date = start_date + timedelta(days=7)

    records, total = await calendar_repo.get_events(
        tenant_id=tenant_id,
        start_date=start_date,
        end_date=end_date,
        search_query=search_query,
    )

    events = [_record_to_event_response(r) for r in records]
    local_google_ids = {e.google_event_id for e in events if e.google_event_id}

    if include_google and user_id_for_google:
        try:
            google_events = await gcal_service.list_events(
                user_id=user_id_for_google,
                start_datetime=datetime.combine(start_date, time.min),
                end_datetime=datetime.combine(end_date, time.max),
            )

            for g_event in google_events:
                if g_event.get("id") in local_google_ids:
                    continue

                local_data = gcal_service.google_event_to_local(g_event)
                events.append(EventResponse(
                    id=UUID("00000000-0000-0000-0000-000000000000"),
                    tenant_id=tenant_id,
                    title=local_data["title"],
                    description=local_data["description"],
                    location=local_data["location"],
                    start_datetime=local_data["start_datetime"],
                    end_datetime=local_data["end_datetime"],
                    timezone=local_data["timezone"],
                    recurrence_rule=None,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                    created_by=None,
                    google_event_id=local_data["google_event_id"],
                    sync_status=SyncStatus.SYNCED,
                    source=EventSource.GOOGLE,
                ))

        except gcal_service.GoogleCalendarError:
            pass

    events.sort(key=lambda e: e.start_datetime)

    return EventListResponse(
        events=events,
        count=len(events),
        date_range=DateRange(start_date=start_date, end_date=end_date),
    )


async def update_event(
    tenant_id: UUID,
    event_id: UUID,
    data: EventUpdate,
    user_id_for_sync: UUID | None = None,
) -> EventResponse:
    """Update an event."""
    existing = await calendar_repo.get_event_by_id(tenant_id, event_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )

    new_start_dt = None
    new_end_dt = None

    if data.event_date or data.start_time:
        current_start = existing["start_datetime"]
        new_date = data.event_date or current_start.date()
        new_time = data.start_time or current_start.time()
        new_start_dt = datetime.combine(new_date, new_time)

        duration = data.duration_minutes or (
            (existing["end_datetime"] - existing["start_datetime"]).seconds // 60
            if existing["end_datetime"] else 60
        )
        new_end_dt = new_start_dt + timedelta(minutes=duration)

    record = await calendar_repo.update_event(
        tenant_id=tenant_id,
        event_id=event_id,
        title=data.title,
        description=data.description,
        location=data.location,
        start_datetime=new_start_dt,
        end_datetime=new_end_dt,
        sync_status="pending_sync" if existing["google_event_id"] else None,
    )

    if existing["google_event_id"] and user_id_for_sync:
        try:
            await gcal_service.update_event(
                user_id=user_id_for_sync,
                google_event_id=existing["google_event_id"],
                title=data.title,
                start_datetime=new_start_dt,
                end_datetime=new_end_dt,
                description=data.description,
                location=data.location,
            )

            await calendar_repo.update_event(
                tenant_id=tenant_id,
                event_id=event_id,
                sync_status="synced",
                last_synced_at=datetime.utcnow(),
            )
        except gcal_service.GoogleCalendarError:
            pass

    return _record_to_event_response(record)


async def delete_event(
    tenant_id: UUID,
    event_id: UUID,
    user_id_for_sync: UUID | None = None,
) -> bool:
    """Delete an event."""
    existing = await calendar_repo.get_event_by_id(tenant_id, event_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )

    if existing["google_event_id"] and user_id_for_sync:
        try:
            await gcal_service.delete_event(
                user_id=user_id_for_sync,
                google_event_id=existing["google_event_id"],
            )
        except gcal_service.GoogleCalendarError:
            pass

    return await calendar_repo.delete_event(tenant_id, event_id)


async def search_events(
    tenant_id: UUID,
    search_query: str,
    limit: int = 10,
) -> list[EventResponse]:
    """Search events by title or description."""
    records = await calendar_repo.search_events(tenant_id, search_query, limit)
    return [_record_to_event_response(r) for r in records]


async def get_next_event(tenant_id: UUID) -> EventResponse | None:
    """Get the next upcoming event."""
    record = await calendar_repo.get_next_event(tenant_id)
    if not record:
        return None
    return _record_to_event_response(record)


# =============================================================================
# Duplicate Detection
# =============================================================================


async def check_for_duplicate(
    tenant_id: UUID,
    start_datetime: datetime,
    title: str,
) -> DuplicateCheckResponse:
    """Check if a similar event already exists."""
    title_words = title.lower().split()
    keyword = title_words[0] if title_words else ""

    duplicate = await calendar_repo.find_potential_duplicate(
        tenant_id=tenant_id,
        start_datetime=start_datetime,
        title_keyword=keyword,
    )

    if duplicate:
        return DuplicateCheckResponse(
            has_duplicate=True,
            existing_event=_record_to_event_response(duplicate),
            similarity_score=0.8,
            message=f"Ya tenés un evento similar: \"{duplicate['title']}\" a las {duplicate['start_datetime'].strftime('%H:%M')}",
        )

    return DuplicateCheckResponse(
        has_duplicate=False,
        existing_event=None,
        similarity_score=0.0,
    )


# =============================================================================
# Availability Check
# =============================================================================


async def check_availability(
    tenant_id: UUID,
    event_date: date,
    event_time: time,
    duration_minutes: int = 60,
    user_id_for_google: UUID | None = None,
) -> AgentAvailabilityResponse:
    """Check availability for a time slot."""
    start_dt = datetime.combine(event_date, event_time)
    end_dt = start_dt + timedelta(minutes=duration_minutes)

    local_events = await calendar_repo.get_events_in_range(
        tenant_id=tenant_id,
        start=start_dt - timedelta(hours=2),
        end=end_dt + timedelta(hours=2),
    )

    conflicts = []

    for record in local_events:
        event_start = record["start_datetime"]
        event_end = record["end_datetime"] or event_start + timedelta(hours=1)

        if event_start < end_dt and event_end > start_dt:
            conflicts.append(_record_to_event_response(record))

    if user_id_for_google:
        try:
            google_events = await gcal_service.list_events(
                user_id=user_id_for_google,
                start_datetime=start_dt - timedelta(hours=2),
                end_datetime=end_dt + timedelta(hours=2),
            )

            for g_event in google_events:
                local_data = gcal_service.google_event_to_local(g_event)
                g_start = local_data["start_datetime"]
                g_end = local_data["end_datetime"] or g_start + timedelta(hours=1)

                if g_start < end_dt and g_end > start_dt:
                    conflicts.append(EventResponse(
                        id=UUID("00000000-0000-0000-0000-000000000000"),
                        tenant_id=tenant_id,
                        title=local_data["title"],
                        description=local_data["description"],
                        location=local_data["location"],
                        start_datetime=g_start,
                        end_datetime=g_end,
                        timezone=local_data["timezone"],
                        recurrence_rule=None,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow(),
                        created_by=None,
                        google_event_id=local_data["google_event_id"],
                        sync_status=SyncStatus.SYNCED,
                        source=EventSource.GOOGLE,
                    ))
        except gcal_service.GoogleCalendarError:
            pass

    suggested_times = []
    if conflicts:
        for hour in range(8, 20):
            test_time = time(hour, 0)
            test_start = datetime.combine(event_date, test_time)
            test_end = test_start + timedelta(minutes=duration_minutes)

            is_free = True
            for conflict in conflicts:
                c_end = conflict.end_datetime or conflict.start_datetime + timedelta(hours=1)
                if conflict.start_datetime < test_end and c_end > test_start:
                    is_free = False
                    break

            if is_free and len(suggested_times) < 3:
                suggested_times.append(test_time)

    return AgentAvailabilityResponse(
        available=len(conflicts) == 0,
        conflicts=conflicts,
        suggested_times=suggested_times,
    )


# =============================================================================
# Google Calendar OAuth
# =============================================================================


async def initiate_google_oauth(
    user_phone: str,
    tenant_id: UUID | None,
    redirect_url: str | None = None,
) -> GoogleOAuthResponse:
    """Initiate Google OAuth flow."""
    state = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(minutes=15)

    await calendar_repo.create_oauth_state(
        state=state,
        user_phone=user_phone,
        tenant_id=tenant_id,
        redirect_url=redirect_url,
        expires_at=expires_at,
    )

    auth_url = gcal_service.generate_auth_url(
        state=state,
        redirect_uri=settings.google_redirect_uri,
    )

    return GoogleOAuthResponse(
        auth_url=auth_url,
        state=state,
        expires_at=expires_at,
    )


async def handle_google_oauth_callback(
    code: str,
    state: str,
) -> tuple[bool, str]:
    """Handle Google OAuth callback."""
    state_record = await calendar_repo.get_oauth_state(state)
    if not state_record:
        return False, "Invalid or expired OAuth state"

    try:
        token_data = await gcal_service.exchange_code_for_tokens(
            code=code,
            redirect_uri=settings.google_redirect_uri,
        )
    except gcal_service.GoogleCalendarError as e:
        return False, str(e.message)

    try:
        user_info = await gcal_service.get_user_info(token_data["access_token"])
    except gcal_service.GoogleCalendarError:
        user_info = {}

    user = await calendar_repo.get_user_by_phone(state_record["user_phone"])
    if not user:
        return False, "User not found"

    expires_at = datetime.utcnow() + timedelta(seconds=token_data.get("expires_in", 3600))

    await calendar_repo.upsert_google_credentials(
        user_id=user["id"],
        tenant_id=user["tenant_id"],
        access_token=token_data["access_token"],
        refresh_token=token_data.get("refresh_token", ""),
        token_expires_at=expires_at,
    )

    await calendar_repo.mark_oauth_state_used(state)

    return True, state_record.get("redirect_url") or settings.calendar_oauth_success_url


async def get_google_connection_status(
    user_id: UUID,
) -> GoogleCalendarConnectionStatus:
    """Get Google Calendar connection status for a user."""
    creds = await calendar_repo.get_google_credentials_by_user(user_id)

    if not creds:
        return GoogleCalendarConnectionStatus(
            connected=False,
            message="Google Calendar no conectado. Conectá tu cuenta para sincronizar eventos.",
        )

    if creds["token_expires_at"] <= datetime.utcnow():
        try:
            await gcal_service.get_valid_credentials(user_id)
            return GoogleCalendarConnectionStatus(
                connected=True,
                calendar_id=creds["calendar_id"],
                expires_at=creds["token_expires_at"],
                message="Google Calendar conectado y sincronizado.",
            )
        except Exception:
            return GoogleCalendarConnectionStatus(
                connected=False,
                message="La conexión con Google Calendar expiró. Reconectá tu cuenta.",
            )

    return GoogleCalendarConnectionStatus(
        connected=True,
        calendar_id=creds["calendar_id"],
        expires_at=creds["token_expires_at"],
        message="Google Calendar conectado y sincronizado.",
    )


# =============================================================================
# Agent Tool Functions
# =============================================================================


async def agent_create_event(
    tenant_id: UUID,
    request: AgentCreateEventRequest,
    created_by: UUID | None = None,
) -> EventWithDuplicateCheck:
    """Create event from agent request."""
    user_id_for_sync = None
    if request.user_phone:
        user = await calendar_repo.get_user_by_phone(request.user_phone)
        if user:
            user_id_for_sync = user["id"]

    data = EventCreate(
        title=request.title,
        event_date=request.event_date,
        start_time=request.start_time,
        duration_minutes=request.duration_minutes,
        location=request.location,
        description=request.description,
    )

    return await create_event(
        tenant_id=tenant_id,
        data=data,
        created_by=created_by,
        sync_to_google=True,
        user_id_for_sync=user_id_for_sync,
    )


async def agent_list_events(
    tenant_id: UUID,
    request: AgentListEventsRequest,
    user_phone: str | None = None,
) -> EventListResponse:
    """List events from agent request."""
    user_id_for_google = None
    if user_phone and request.include_google:
        user = await calendar_repo.get_user_by_phone(user_phone)
        if user:
            user_id_for_google = user["id"]

    return await list_events(
        tenant_id=tenant_id,
        start_date=request.event_date or request.start_date,
        end_date=request.end_date or request.event_date,
        search_query=request.search_query,
        include_google=request.include_google,
        user_id_for_google=user_id_for_google,
    )


async def agent_detect_event(
    tenant_id: UUID,
    request: AgentDetectEventRequest,
) -> AgentDetectEventResponse:
    """Detect if message contains an event to schedule."""
    return await detect_event_in_message(
        message=request.message,
        user_phone=request.user_phone,
        context=request.context,
    )


# =============================================================================
# Helper Functions
# =============================================================================


def _record_to_event_response(record) -> EventResponse:
    """Convert database record to EventResponse."""
    return EventResponse(
        id=record["id"],
        tenant_id=record["tenant_id"],
        title=record["title"],
        description=record.get("description"),
        location=record.get("location"),
        start_datetime=record["start_datetime"],
        end_datetime=record.get("end_datetime"),
        timezone=record.get("timezone", "America/Argentina/Buenos_Aires"),
        recurrence_rule=record.get("recurrence_rule"),
        created_at=record["created_at"],
        updated_at=record.get("updated_at", record["created_at"]),
        created_by=record.get("created_by"),
        google_event_id=record.get("google_event_id"),
        google_calendar_id=record.get("google_calendar_id"),
        sync_status=SyncStatus(record.get("sync_status", "local")),
        source=EventSource(record.get("source", "app")),
    )
