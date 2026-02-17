"""Calendar repository for events and Google Calendar credentials."""

from datetime import date, datetime, time, timedelta
from uuid import UUID

import asyncpg

from ..config.database import fetch_all, fetch_one, get_connection


# =============================================================================
# Events
# =============================================================================


async def create_event(
    tenant_id: UUID,
    title: str,
    start_datetime: datetime,
    end_datetime: datetime | None = None,
    description: str | None = None,
    location: str | None = None,
    timezone: str = "America/Argentina/Buenos_Aires",
    recurrence_rule: str | None = None,
    created_by: UUID | None = None,
    idempotency_key: str | None = None,
    google_event_id: str | None = None,
    google_calendar_id: str | None = None,
    sync_status: str = "local",
    source: str = "app",
) -> asyncpg.Record:
    """Create a new event."""
    query = """
        INSERT INTO events (
            tenant_id, title, description, location, start_datetime, end_datetime,
            timezone, recurrence_rule, created_by, idempotency_key,
            google_event_id, google_calendar_id, sync_status, source
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
        ON CONFLICT (tenant_id, idempotency_key) WHERE idempotency_key IS NOT NULL
        DO UPDATE SET id = events.id
        RETURNING *
    """
    return await fetch_one(
        query,
        tenant_id,
        title,
        description,
        location,
        start_datetime,
        end_datetime,
        timezone,
        recurrence_rule,
        created_by,
        idempotency_key,
        google_event_id,
        google_calendar_id,
        sync_status,
        source,
    )


async def get_event_by_id(tenant_id: UUID, event_id: UUID) -> asyncpg.Record | None:
    """Get an event by ID."""
    query = """
        SELECT *
        FROM events
        WHERE tenant_id = $1 AND id = $2
    """
    return await fetch_one(query, tenant_id, event_id)


async def get_event_by_google_id(
    tenant_id: UUID, google_event_id: str
) -> asyncpg.Record | None:
    """Get an event by Google Calendar event ID."""
    query = """
        SELECT *
        FROM events
        WHERE tenant_id = $1 AND google_event_id = $2
    """
    return await fetch_one(query, tenant_id, google_event_id)


async def get_events(
    tenant_id: UUID,
    start_date: date | None = None,
    end_date: date | None = None,
    search_query: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[asyncpg.Record], int]:
    """Get events with filters and pagination."""
    conditions = ["tenant_id = $1"]
    params: list = [tenant_id]
    param_idx = 2

    if start_date:
        conditions.append(f"start_datetime >= ${param_idx}")
        params.append(datetime.combine(start_date, time.min))
        param_idx += 1

    if end_date:
        conditions.append(f"start_datetime <= ${param_idx}")
        params.append(datetime.combine(end_date, time.max))
        param_idx += 1

    if search_query:
        conditions.append(f"(LOWER(title) LIKE LOWER(${param_idx}) OR LOWER(description) LIKE LOWER(${param_idx}))")
        params.append(f"%{search_query}%")
        param_idx += 1

    where_clause = " AND ".join(conditions)

    count_query = f"""
        SELECT COUNT(*) as total
        FROM events
        WHERE {where_clause}
    """

    data_query = f"""
        SELECT *
        FROM events
        WHERE {where_clause}
        ORDER BY start_datetime ASC
        LIMIT ${param_idx} OFFSET ${param_idx + 1}
    """
    params.extend([limit, offset])

    async with get_connection() as conn:
        count_result = await conn.fetchrow(count_query, *params[:-2])
        total = count_result["total"] if count_result else 0
        events = await conn.fetch(data_query, *params)

    return events, total


async def get_events_by_date(tenant_id: UUID, event_date: date) -> list[asyncpg.Record]:
    """Get all events for a specific date."""
    query = """
        SELECT *
        FROM events
        WHERE tenant_id = $1
          AND start_datetime >= $2
          AND start_datetime < $3
        ORDER BY start_datetime ASC
    """
    start = datetime.combine(event_date, time.min)
    end = datetime.combine(event_date + timedelta(days=1), time.min)
    return await fetch_all(query, tenant_id, start, end)


async def get_events_in_range(
    tenant_id: UUID, start: datetime, end: datetime
) -> list[asyncpg.Record]:
    """Get events within a datetime range."""
    query = """
        SELECT *
        FROM events
        WHERE tenant_id = $1
          AND start_datetime >= $2
          AND start_datetime <= $3
        ORDER BY start_datetime ASC
    """
    return await fetch_all(query, tenant_id, start, end)


async def find_potential_duplicate(
    tenant_id: UUID,
    start_datetime: datetime,
    title_keyword: str,
    minutes_threshold: int = 30,
) -> asyncpg.Record | None:
    """Find potential duplicate event based on time and title similarity."""
    query = """
        SELECT *
        FROM events
        WHERE tenant_id = $1
          AND ABS(EXTRACT(EPOCH FROM start_datetime - $2)) < $3
          AND LOWER(title) LIKE LOWER($4)
        LIMIT 1
    """
    return await fetch_one(
        query,
        tenant_id,
        start_datetime,
        minutes_threshold * 60,
        f"%{title_keyword}%",
    )


async def search_events(
    tenant_id: UUID,
    search_query: str,
    limit: int = 10,
) -> list[asyncpg.Record]:
    """Search events by title or description."""
    query = """
        SELECT *
        FROM events
        WHERE tenant_id = $1
          AND (
            LOWER(title) LIKE LOWER($2)
            OR LOWER(description) LIKE LOWER($2)
          )
        ORDER BY start_datetime DESC
        LIMIT $3
    """
    return await fetch_all(query, tenant_id, f"%{search_query}%", limit)


async def get_next_event(tenant_id: UUID) -> asyncpg.Record | None:
    """Get the next upcoming event."""
    query = """
        SELECT *
        FROM events
        WHERE tenant_id = $1
          AND start_datetime >= NOW()
        ORDER BY start_datetime ASC
        LIMIT 1
    """
    return await fetch_one(query, tenant_id)


async def update_event(
    tenant_id: UUID,
    event_id: UUID,
    title: str | None = None,
    description: str | None = None,
    location: str | None = None,
    start_datetime: datetime | None = None,
    end_datetime: datetime | None = None,
    recurrence_rule: str | None = None,
    sync_status: str | None = None,
    google_event_id: str | None = None,
    last_synced_at: datetime | None = None,
) -> asyncpg.Record | None:
    """Update an event."""
    updates = ["updated_at = NOW()"]
    params = [tenant_id, event_id]
    param_idx = 3

    if title is not None:
        updates.append(f"title = ${param_idx}")
        params.append(title)
        param_idx += 1

    if description is not None:
        updates.append(f"description = ${param_idx}")
        params.append(description)
        param_idx += 1

    if location is not None:
        updates.append(f"location = ${param_idx}")
        params.append(location)
        param_idx += 1

    if start_datetime is not None:
        updates.append(f"start_datetime = ${param_idx}")
        params.append(start_datetime)
        param_idx += 1

    if end_datetime is not None:
        updates.append(f"end_datetime = ${param_idx}")
        params.append(end_datetime)
        param_idx += 1

    if recurrence_rule is not None:
        updates.append(f"recurrence_rule = ${param_idx}")
        params.append(recurrence_rule)
        param_idx += 1

    if sync_status is not None:
        updates.append(f"sync_status = ${param_idx}")
        params.append(sync_status)
        param_idx += 1

    if google_event_id is not None:
        updates.append(f"google_event_id = ${param_idx}")
        params.append(google_event_id)
        param_idx += 1

    if last_synced_at is not None:
        updates.append(f"last_synced_at = ${param_idx}")
        params.append(last_synced_at)
        param_idx += 1

    query = f"""
        UPDATE events
        SET {', '.join(updates)}
        WHERE tenant_id = $1 AND id = $2
        RETURNING *
    """
    return await fetch_one(query, *params)


async def delete_event(tenant_id: UUID, event_id: UUID) -> bool:
    """Delete an event."""
    async with get_connection() as conn:
        result = await conn.execute(
            "DELETE FROM events WHERE tenant_id = $1 AND id = $2",
            tenant_id,
            event_id,
        )
        return result == "DELETE 1"


async def get_events_pending_sync(tenant_id: UUID) -> list[asyncpg.Record]:
    """Get events pending sync to Google Calendar."""
    query = """
        SELECT *
        FROM events
        WHERE tenant_id = $1 AND sync_status = 'pending_sync'
        ORDER BY created_at ASC
    """
    return await fetch_all(query, tenant_id)


# =============================================================================
# Google Calendar Credentials
# =============================================================================


async def get_google_credentials_by_user(
    user_id: UUID,
) -> asyncpg.Record | None:
    """Get Google Calendar credentials for a user."""
    query = """
        SELECT *
        FROM google_calendar_credentials
        WHERE user_id = $1
    """
    return await fetch_one(query, user_id)


async def get_google_credentials_by_tenant(
    tenant_id: UUID,
) -> list[asyncpg.Record]:
    """Get all Google Calendar credentials for a tenant."""
    query = """
        SELECT gcc.*, u.phone, u.display_name
        FROM google_calendar_credentials gcc
        JOIN users u ON gcc.user_id = u.id
        WHERE gcc.tenant_id = $1
    """
    return await fetch_all(query, tenant_id)


async def upsert_google_credentials(
    user_id: UUID,
    tenant_id: UUID,
    access_token: str,
    refresh_token: str,
    token_expires_at: datetime,
    calendar_id: str = "primary",
    scopes: list[str] | None = None,
) -> asyncpg.Record:
    """Create or update Google Calendar credentials."""
    if scopes is None:
        scopes = [
            "https://www.googleapis.com/auth/calendar.events",
            "https://www.googleapis.com/auth/calendar.readonly",
        ]

    query = """
        INSERT INTO google_calendar_credentials (
            user_id, tenant_id, access_token, refresh_token,
            token_expires_at, calendar_id, scopes
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        ON CONFLICT (user_id)
        DO UPDATE SET
            access_token = EXCLUDED.access_token,
            refresh_token = EXCLUDED.refresh_token,
            token_expires_at = EXCLUDED.token_expires_at,
            calendar_id = EXCLUDED.calendar_id,
            scopes = EXCLUDED.scopes,
            updated_at = NOW()
        RETURNING *
    """
    return await fetch_one(
        query, user_id, tenant_id, access_token, refresh_token,
        token_expires_at, calendar_id, scopes,
    )


async def update_google_tokens(
    user_id: UUID,
    access_token: str,
    token_expires_at: datetime,
    refresh_token: str | None = None,
) -> asyncpg.Record | None:
    """Update OAuth tokens after refresh."""
    if refresh_token:
        query = """
            UPDATE google_calendar_credentials
            SET access_token = $2,
                refresh_token = $3,
                token_expires_at = $4,
                updated_at = NOW()
            WHERE user_id = $1
            RETURNING *
        """
        return await fetch_one(query, user_id, access_token, refresh_token, token_expires_at)
    else:
        query = """
            UPDATE google_calendar_credentials
            SET access_token = $2,
                token_expires_at = $3,
                updated_at = NOW()
            WHERE user_id = $1
            RETURNING *
        """
        return await fetch_one(query, user_id, access_token, token_expires_at)


async def delete_google_credentials(user_id: UUID) -> bool:
    """Delete Google Calendar credentials for a user."""
    async with get_connection() as conn:
        result = await conn.execute(
            "DELETE FROM google_calendar_credentials WHERE user_id = $1",
            user_id,
        )
        return result == "DELETE 1"


# =============================================================================
# OAuth States
# =============================================================================


async def create_oauth_state(
    state: str,
    user_phone: str,
    tenant_id: UUID | None,
    redirect_url: str | None,
    expires_at: datetime,
) -> asyncpg.Record:
    """Create OAuth state for tracking callback."""
    query = """
        INSERT INTO oauth_states (state, user_phone, tenant_id, redirect_url, expires_at)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING *
    """
    return await fetch_one(query, state, user_phone, tenant_id, redirect_url, expires_at)


async def get_oauth_state(state: str) -> asyncpg.Record | None:
    """Get OAuth state by state token."""
    query = """
        SELECT *
        FROM oauth_states
        WHERE state = $1
          AND used_at IS NULL
          AND expires_at > NOW()
    """
    return await fetch_one(query, state)


async def mark_oauth_state_used(state: str) -> asyncpg.Record | None:
    """Mark OAuth state as used."""
    query = """
        UPDATE oauth_states
        SET used_at = NOW()
        WHERE state = $1
        RETURNING *
    """
    return await fetch_one(query, state)


async def cleanup_expired_oauth_states() -> int:
    """Delete expired OAuth states."""
    async with get_connection() as conn:
        result = await conn.execute(
            "DELETE FROM oauth_states WHERE expires_at < NOW()"
        )
        return int(result.split()[1]) if result else 0


# =============================================================================
# User Lookups (for agent)
# =============================================================================


async def get_user_by_phone(phone: str) -> asyncpg.Record | None:
    """Get user by phone number.

    Normalizes phone to E.164 format and searches with variants
    to handle Argentina mobile numbers (with/without '9' prefix).
    """
    normalized = phone.strip()
    if not normalized.startswith("+"):
        normalized = f"+{normalized}"

    # Argentina mobile normalization: +54XX → +549XX
    if normalized.startswith("+54") and not normalized.startswith("+549"):
        rest = normalized[3:]
        if len(rest) == 10:
            normalized = f"+549{rest}"

    phone_variants = [normalized]
    if normalized.startswith("+549"):
        phone_variants.append(f"+54{normalized[4:]}")

    query = """
        SELECT id, tenant_id, phone, email, display_name, role
        FROM users
        WHERE phone = ANY($1)
          AND is_active = true
    """
    return await fetch_one(query, phone_variants)


async def get_user_by_id(user_id: UUID) -> asyncpg.Record | None:
    """Get user by ID."""
    query = """
        SELECT id, tenant_id, phone, email, display_name, role
        FROM users
        WHERE id = $1
    """
    return await fetch_one(query, user_id)
