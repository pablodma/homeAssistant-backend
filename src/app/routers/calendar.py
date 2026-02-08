"""Calendar endpoints for events and Google Calendar integration."""

from datetime import date, time
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import RedirectResponse

from ..config.settings import get_settings
from ..middleware.auth import get_current_user, validate_tenant_access
from ..schemas.auth import CurrentUser
from ..schemas.calendar import (
    AgentAvailabilityResponse,
    AgentCreateEventRequest,
    AgentDetectEventRequest,
    AgentDetectEventResponse,
    AgentListEventsRequest,
    AgentUpdateEventRequest,
    EventCreate,
    EventListResponse,
    EventResponse,
    EventUpdate,
    EventWithDuplicateCheck,
    GoogleCalendarConnectionStatus,
    GoogleOAuthInitiate,
    GoogleOAuthResponse,
)
from ..services import calendar as calendar_service

settings = get_settings()

router = APIRouter(prefix="/tenants/{tenant_id}", tags=["Calendar"])


# =============================================================================
# Event CRUD Endpoints
# =============================================================================


@router.get("/events", response_model=EventListResponse)
async def get_events(
    tenant_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    _: Annotated[None, Depends(validate_tenant_access)],
    start_date: date | None = Query(None, description="Start date filter"),
    end_date: date | None = Query(None, description="End date filter"),
    search: str | None = Query(None, description="Search in title/description"),
    include_google: bool = Query(True, description="Include Google Calendar events"),
) -> EventListResponse:
    """Get events with optional filters."""
    return await calendar_service.list_events(
        tenant_id=tenant_id,
        start_date=start_date,
        end_date=end_date,
        search_query=search,
        include_google=include_google,
        user_id_for_google=current_user.id,
    )


@router.post(
    "/events",
    response_model=EventWithDuplicateCheck,
    status_code=status.HTTP_201_CREATED,
)
async def create_event(
    tenant_id: UUID,
    request: EventCreate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    _: Annotated[None, Depends(validate_tenant_access)],
) -> EventWithDuplicateCheck:
    """Create a new event with duplicate detection and Google Calendar sync."""
    return await calendar_service.create_event(
        tenant_id=tenant_id,
        data=request,
        created_by=current_user.id,
        sync_to_google=True,
        user_id_for_sync=current_user.id,
    )


@router.get("/events/{event_id}", response_model=EventResponse)
async def get_event(
    tenant_id: UUID,
    event_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    _: Annotated[None, Depends(validate_tenant_access)],
) -> EventResponse:
    """Get a single event by ID."""
    return await calendar_service.get_event(tenant_id, event_id)


@router.put("/events/{event_id}", response_model=EventResponse)
async def update_event(
    tenant_id: UUID,
    event_id: UUID,
    request: EventUpdate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    _: Annotated[None, Depends(validate_tenant_access)],
) -> EventResponse:
    """Update an existing event."""
    return await calendar_service.update_event(
        tenant_id=tenant_id,
        event_id=event_id,
        data=request,
        user_id_for_sync=current_user.id,
    )


@router.delete("/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(
    tenant_id: UUID,
    event_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    _: Annotated[None, Depends(validate_tenant_access)],
) -> None:
    """Delete an event."""
    await calendar_service.delete_event(
        tenant_id=tenant_id,
        event_id=event_id,
        user_id_for_sync=current_user.id,
    )


# =============================================================================
# Google Calendar Connection Endpoints
# =============================================================================


@router.get("/calendar/connection", response_model=GoogleCalendarConnectionStatus)
async def get_google_connection_status(
    tenant_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    _: Annotated[None, Depends(validate_tenant_access)],
) -> GoogleCalendarConnectionStatus:
    """Get Google Calendar connection status for the current user."""
    return await calendar_service.get_google_connection_status(current_user.id)


@router.post("/calendar/connect", response_model=GoogleOAuthResponse)
async def initiate_google_oauth(
    tenant_id: UUID,
    request: GoogleOAuthInitiate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    _: Annotated[None, Depends(validate_tenant_access)],
) -> GoogleOAuthResponse:
    """Initiate Google OAuth flow to connect calendar."""
    return await calendar_service.initiate_google_oauth(
        user_phone=request.user_phone,
        tenant_id=tenant_id,
        redirect_url=request.redirect_url,
    )


# =============================================================================
# Agent Tool Endpoints (for n8n HTTP Request)
# =============================================================================


@router.post(
    "/agent/calendar/event",
    response_model=EventWithDuplicateCheck,
    status_code=status.HTTP_201_CREATED,
    tags=["Agent"],
)
async def agent_create_event(
    tenant_id: UUID,
    request: AgentCreateEventRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    _: Annotated[None, Depends(validate_tenant_access)],
) -> EventWithDuplicateCheck:
    """Create event from agent (n8n). Used by Calendar Agent in n8n workflows."""
    return await calendar_service.agent_create_event(
        tenant_id=tenant_id,
        request=request,
        created_by=current_user.id,
    )


@router.get(
    "/agent/calendar/events",
    response_model=EventListResponse,
    tags=["Agent"],
)
async def agent_list_events(
    tenant_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    _: Annotated[None, Depends(validate_tenant_access)],
    date_filter: date | None = Query(None, alias="date", description="Specific date"),
    start_date: date | None = Query(None, description="Range start"),
    end_date: date | None = Query(None, description="Range end"),
    search_query: str | None = Query(None, alias="search", description="Search term"),
    include_google: bool = Query(True, description="Include Google events"),
    user_phone: str | None = Query(None, description="User phone for Google lookup"),
) -> EventListResponse:
    """List events for agent (n8n)."""

    request = AgentListEventsRequest(
        date=date_filter,
        start_date=start_date,
        end_date=end_date,
        search_query=search_query,
        include_google=include_google,
    )

    return await calendar_service.agent_list_events(
        tenant_id=tenant_id,
        request=request,
        user_phone=user_phone,
    )


@router.put(
    "/agent/calendar/event/{event_id}",
    response_model=EventResponse,
    tags=["Agent"],
)
async def agent_update_event(
    tenant_id: UUID,
    event_id: UUID,
    request: AgentUpdateEventRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    _: Annotated[None, Depends(validate_tenant_access)],
) -> EventResponse:
    """Update event from agent (n8n)."""

    update_data = EventUpdate(
        title=request.title,
        date=request.date,
        start_time=request.start_time,
        duration_minutes=request.duration_minutes,
        location=request.location,
    )

    return await calendar_service.update_event(
        tenant_id=tenant_id,
        event_id=event_id,
        data=update_data,
        user_id_for_sync=current_user.id,
    )


@router.delete(
    "/agent/calendar/event/{event_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Agent"],
)
async def agent_delete_event(
    tenant_id: UUID,
    event_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    _: Annotated[None, Depends(validate_tenant_access)],
) -> None:
    """Delete event from agent (n8n)."""
    await calendar_service.delete_event(
        tenant_id=tenant_id,
        event_id=event_id,
        user_id_for_sync=current_user.id,
    )


@router.get(
    "/agent/calendar/availability",
    response_model=AgentAvailabilityResponse,
    tags=["Agent"],
)
async def agent_check_availability(
    tenant_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    _: Annotated[None, Depends(validate_tenant_access)],
    date_check: date = Query(..., alias="date", description="Date to check"),
    time_check: time = Query(..., alias="time", description="Time to check (HH:MM)"),
    duration: int = Query(60, description="Duration in minutes"),
    user_phone: str | None = Query(None, description="User phone for Google lookup"),
) -> AgentAvailabilityResponse:
    """Check availability for a time slot."""

    user_id_for_google = None
    if user_phone:
        from ..repositories import calendar_repo
        user = await calendar_repo.get_user_by_phone(user_phone)
        if user:
            user_id_for_google = user["id"]

    return await calendar_service.check_availability(
        tenant_id=tenant_id,
        event_date=date_check,
        event_time=time_check,
        duration_minutes=duration,
        user_id_for_google=user_id_for_google,
    )


@router.post(
    "/agent/calendar/detect",
    response_model=AgentDetectEventResponse,
    tags=["Agent"],
)
async def agent_detect_event(
    tenant_id: UUID,
    request: AgentDetectEventRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    _: Annotated[None, Depends(validate_tenant_access)],
) -> AgentDetectEventResponse:
    """Detect if a message contains an event to schedule using NLP."""
    return await calendar_service.agent_detect_event(
        tenant_id=tenant_id,
        request=request,
    )


@router.get(
    "/agent/calendar/connection-status",
    response_model=GoogleCalendarConnectionStatus,
    tags=["Agent"],
)
async def agent_get_connection_status(
    tenant_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    _: Annotated[None, Depends(validate_tenant_access)],
    user_phone: str | None = Query(None, description="User phone to check"),
) -> GoogleCalendarConnectionStatus:
    """Get Google Calendar connection status for agent."""

    user_id = current_user.id
    if user_phone:
        from ..repositories import calendar_repo
        user = await calendar_repo.get_user_by_phone(user_phone)
        if user:
            user_id = user["id"]

    status_response = await calendar_service.get_google_connection_status(user_id)

    if not status_response.connected and user_phone:
        oauth_response = await calendar_service.initiate_google_oauth(
            user_phone=user_phone,
            tenant_id=tenant_id,
        )
        status_response.auth_url = oauth_response.auth_url

    return status_response


@router.get(
    "/agent/calendar/next",
    response_model=EventResponse | None,
    tags=["Agent"],
)
async def agent_get_next_event(
    tenant_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    _: Annotated[None, Depends(validate_tenant_access)],
) -> EventResponse | None:
    """Get the next upcoming event."""
    return await calendar_service.get_next_event(tenant_id)


# =============================================================================
# OAuth Callback Router (separate, no tenant prefix)
# =============================================================================

oauth_router = APIRouter(tags=["OAuth"])


@oauth_router.get("/auth/google/callback")
async def google_oauth_callback(
    code: str = Query(..., description="Authorization code from Google"),
    state: str = Query(..., description="State token for validation"),
) -> RedirectResponse:
    """Handle Google OAuth callback."""
    success, redirect_url = await calendar_service.handle_google_oauth_callback(
        code=code,
        state=state,
    )

    if success:
        return RedirectResponse(url=redirect_url)
    else:
        error_url = f"{settings.calendar_oauth_error_url}?error={redirect_url}"
        return RedirectResponse(url=error_url)


@oauth_router.get("/auth/google/success")
async def google_oauth_success():
    """Display success page after Google Calendar connection."""
    from fastapi.responses import HTMLResponse
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Calendario Conectado</title>
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; 
                   display: flex; justify-content: center; align-items: center;
                   min-height: 100vh; margin: 0; background: #f0fdf4; }
            .card { text-align: center; padding: 40px; background: white;
                    border-radius: 16px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
            .icon { font-size: 64px; margin-bottom: 16px; }
            h1 { color: #166534; margin: 0 0 8px; }
            p { color: #6b7280; margin: 0; }
        </style>
    </head>
    <body>
        <div class="card">
            <div class="icon">✅</div>
            <h1>Calendario conectado</h1>
            <p>Ya podes cerrar esta ventana y volver a WhatsApp.</p>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html)


@oauth_router.get("/auth/google/error")
async def google_oauth_error(error: str = Query(None)):
    """Display error page for Google Calendar connection failure."""
    from fastapi.responses import HTMLResponse
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Error de Conexion</title>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; 
                   display: flex; justify-content: center; align-items: center;
                   min-height: 100vh; margin: 0; background: #fef2f2; }}
            .card {{ text-align: center; padding: 40px; background: white;
                    border-radius: 16px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
            .icon {{ font-size: 64px; margin-bottom: 16px; }}
            h1 {{ color: #dc2626; margin: 0 0 8px; }}
            p {{ color: #6b7280; margin: 0; }}
            .error {{ font-size: 12px; color: #9ca3af; margin-top: 16px; }}
        </style>
    </head>
    <body>
        <div class="card">
            <div class="icon">❌</div>
            <h1>Error al conectar</h1>
            <p>No se pudo conectar tu Google Calendar.</p>
            <p>Intenta de nuevo desde WhatsApp.</p>
            <p class="error">{error or ''}</p>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html)
