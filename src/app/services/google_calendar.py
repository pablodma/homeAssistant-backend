"""Google Calendar API wrapper service."""

from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlencode
from uuid import UUID

import httpx
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from ..config.settings import get_settings
from ..repositories import calendar_repo

settings = get_settings()

# Google Calendar API scopes
SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.readonly",
]

# OAuth endpoints
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"


class GoogleCalendarError(Exception):
    """Custom exception for Google Calendar operations."""

    def __init__(self, message: str, error_code: str | None = None):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)


# =============================================================================
# OAuth Flow
# =============================================================================


def generate_auth_url(state: str, redirect_uri: str) -> str:
    """Generate Google OAuth authorization URL."""
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(SCOPES + ["openid", "email", "profile"]),
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


async def exchange_code_for_tokens(
    code: str, redirect_uri: str
) -> dict[str, Any]:
    """Exchange authorization code for access and refresh tokens."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            },
        )

        if response.status_code != 200:
            raise GoogleCalendarError(
                f"Token exchange failed: {response.text}",
                error_code="token_exchange_failed",
            )

        return response.json()


async def refresh_access_token(refresh_token: str) -> dict[str, Any]:
    """Refresh access token using refresh token."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )

        if response.status_code != 200:
            raise GoogleCalendarError(
                f"Token refresh failed: {response.text}",
                error_code="token_refresh_failed",
            )

        return response.json()


async def get_user_info(access_token: str) -> dict[str, Any]:
    """Get user info from Google."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )

        if response.status_code != 200:
            raise GoogleCalendarError(
                "Failed to get user info",
                error_code="userinfo_failed",
            )

        return response.json()


# =============================================================================
# Credentials Management
# =============================================================================


async def get_valid_credentials(user_id: UUID) -> Credentials | None:
    """Get valid Google credentials for a user, refreshing if necessary."""
    creds_record = await calendar_repo.get_google_credentials_by_user(user_id)
    if not creds_record:
        return None

    creds = Credentials(
        token=creds_record["access_token"],
        refresh_token=creds_record["refresh_token"],
        token_uri=GOOGLE_TOKEN_URL,
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        scopes=creds_record["scopes"],
    )

    # Check if token needs refresh (with 5 min buffer)
    if creds_record["token_expires_at"] <= datetime.utcnow() + timedelta(minutes=5):
        try:
            token_data = await refresh_access_token(creds_record["refresh_token"])
            expires_at = datetime.utcnow() + timedelta(seconds=token_data["expires_in"])

            await calendar_repo.update_google_tokens(
                user_id=user_id,
                access_token=token_data["access_token"],
                token_expires_at=expires_at,
                refresh_token=token_data.get("refresh_token"),
            )

            creds = Credentials(
                token=token_data["access_token"],
                refresh_token=token_data.get("refresh_token", creds_record["refresh_token"]),
                token_uri=GOOGLE_TOKEN_URL,
                client_id=settings.google_client_id,
                client_secret=settings.google_client_secret,
                scopes=creds_record["scopes"],
            )
        except GoogleCalendarError:
            return None

    return creds


def _build_calendar_service(credentials: Credentials):
    """Build Google Calendar service client."""
    return build("calendar", "v3", credentials=credentials)


# =============================================================================
# Calendar Events Operations
# =============================================================================


async def create_event(
    user_id: UUID,
    title: str,
    start_datetime: datetime,
    end_datetime: datetime,
    description: str | None = None,
    location: str | None = None,
    timezone: str = "America/Argentina/Buenos_Aires",
    calendar_id: str = "primary",
) -> dict[str, Any]:
    """Create an event in Google Calendar."""
    creds = await get_valid_credentials(user_id)
    if not creds:
        raise GoogleCalendarError(
            "No valid Google credentials",
            error_code="no_credentials",
        )

    service = _build_calendar_service(creds)

    event_body = {
        "summary": title,
        "start": {
            "dateTime": start_datetime.isoformat(),
            "timeZone": timezone,
        },
        "end": {
            "dateTime": end_datetime.isoformat(),
            "timeZone": timezone,
        },
    }

    if description:
        event_body["description"] = description

    if location:
        event_body["location"] = location

    try:
        event = service.events().insert(
            calendarId=calendar_id,
            body=event_body,
        ).execute()
        return event
    except HttpError as e:
        raise GoogleCalendarError(
            f"Failed to create event: {e.reason}",
            error_code="create_failed",
        )


async def update_event(
    user_id: UUID,
    google_event_id: str,
    title: str | None = None,
    start_datetime: datetime | None = None,
    end_datetime: datetime | None = None,
    description: str | None = None,
    location: str | None = None,
    timezone: str = "America/Argentina/Buenos_Aires",
    calendar_id: str = "primary",
) -> dict[str, Any]:
    """Update an event in Google Calendar."""
    creds = await get_valid_credentials(user_id)
    if not creds:
        raise GoogleCalendarError(
            "No valid Google credentials",
            error_code="no_credentials",
        )

    service = _build_calendar_service(creds)

    try:
        existing = service.events().get(
            calendarId=calendar_id,
            eventId=google_event_id,
        ).execute()

        if title:
            existing["summary"] = title
        if description is not None:
            existing["description"] = description
        if location is not None:
            existing["location"] = location
        if start_datetime:
            existing["start"] = {
                "dateTime": start_datetime.isoformat(),
                "timeZone": timezone,
            }
        if end_datetime:
            existing["end"] = {
                "dateTime": end_datetime.isoformat(),
                "timeZone": timezone,
            }

        updated = service.events().update(
            calendarId=calendar_id,
            eventId=google_event_id,
            body=existing,
        ).execute()
        return updated
    except HttpError as e:
        raise GoogleCalendarError(
            f"Failed to update event: {e.reason}",
            error_code="update_failed",
        )


async def delete_event(
    user_id: UUID,
    google_event_id: str,
    calendar_id: str = "primary",
) -> bool:
    """Delete an event from Google Calendar."""
    creds = await get_valid_credentials(user_id)
    if not creds:
        raise GoogleCalendarError(
            "No valid Google credentials",
            error_code="no_credentials",
        )

    service = _build_calendar_service(creds)

    try:
        service.events().delete(
            calendarId=calendar_id,
            eventId=google_event_id,
        ).execute()
        return True
    except HttpError as e:
        if e.resp.status == 404:
            return True
        raise GoogleCalendarError(
            f"Failed to delete event: {e.reason}",
            error_code="delete_failed",
        )


async def list_events(
    user_id: UUID,
    start_datetime: datetime,
    end_datetime: datetime,
    calendar_id: str = "primary",
    max_results: int = 50,
) -> list[dict[str, Any]]:
    """List events from Google Calendar within a date range."""
    creds = await get_valid_credentials(user_id)
    if not creds:
        raise GoogleCalendarError(
            "No valid Google credentials",
            error_code="no_credentials",
        )

    service = _build_calendar_service(creds)

    try:
        events_result = service.events().list(
            calendarId=calendar_id,
            timeMin=start_datetime.isoformat() + "Z",
            timeMax=end_datetime.isoformat() + "Z",
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        ).execute()
        return events_result.get("items", [])
    except HttpError as e:
        raise GoogleCalendarError(
            f"Failed to list events: {e.reason}",
            error_code="list_failed",
        )


async def get_event(
    user_id: UUID,
    google_event_id: str,
    calendar_id: str = "primary",
) -> dict[str, Any] | None:
    """Get a single event from Google Calendar."""
    creds = await get_valid_credentials(user_id)
    if not creds:
        return None

    service = _build_calendar_service(creds)

    try:
        event = service.events().get(
            calendarId=calendar_id,
            eventId=google_event_id,
        ).execute()
        return event
    except HttpError as e:
        if e.resp.status == 404:
            return None
        raise GoogleCalendarError(
            f"Failed to get event: {e.reason}",
            error_code="get_failed",
        )


# =============================================================================
# Helper Functions
# =============================================================================


def parse_google_datetime(google_dt: dict[str, Any]) -> datetime:
    """Parse Google Calendar datetime format to Python datetime."""
    if "dateTime" in google_dt:
        dt_str = google_dt["dateTime"]
        if "+" in dt_str:
            dt_str = dt_str.split("+")[0]
        elif "Z" in dt_str:
            dt_str = dt_str.replace("Z", "")
        return datetime.fromisoformat(dt_str)
    elif "date" in google_dt:
        return datetime.strptime(google_dt["date"], "%Y-%m-%d")
    else:
        raise ValueError("Invalid Google datetime format")


def google_event_to_local(google_event: dict[str, Any]) -> dict[str, Any]:
    """Convert Google Calendar event to local event format."""
    start_dt = parse_google_datetime(google_event.get("start", {}))
    end_dt = parse_google_datetime(google_event.get("end", {})) if google_event.get("end") else None

    return {
        "google_event_id": google_event.get("id"),
        "title": google_event.get("summary", "Sin título"),
        "description": google_event.get("description"),
        "location": google_event.get("location"),
        "start_datetime": start_dt,
        "end_datetime": end_dt,
        "timezone": google_event.get("start", {}).get("timeZone", "America/Argentina/Buenos_Aires"),
        "source": "google",
    }
