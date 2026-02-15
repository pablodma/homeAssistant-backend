"""Database connection management."""

import json
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import asyncpg
from asyncpg import Pool

from .settings import get_settings

# Global connection pool
_pool: Pool | None = None


def _json_encoder(value):
    """Encode Python objects to JSON string for PostgreSQL json/jsonb columns.

    Backward-compatible: if value is already a JSON string (from existing
    json.dumps() calls), returns it as-is. Otherwise serializes with default=str
    to handle datetime and UUID objects.
    """
    if isinstance(value, str):
        return value
    return json.dumps(value, default=str)


def _json_decoder(value):
    """Decode JSON string from PostgreSQL to Python objects."""
    if isinstance(value, str):
        return json.loads(value)
    return value


async def _init_connection(conn: asyncpg.Connection):
    """Initialize each connection with custom JSON/JSONB codecs.

    By default asyncpg returns json/jsonb as raw strings. This registers
    codecs so they're automatically decoded to Python dicts/lists.
    """
    await conn.set_type_codec(
        "json",
        encoder=_json_encoder,
        decoder=_json_decoder,
        schema="pg_catalog",
    )
    await conn.set_type_codec(
        "jsonb",
        encoder=_json_encoder,
        decoder=_json_decoder,
        schema="pg_catalog",
    )


async def create_pool() -> Pool:
    """Create database connection pool."""
    settings = get_settings()
    return await asyncpg.create_pool(
        dsn=settings.database_url,
        min_size=2,
        max_size=10,
        command_timeout=60,
        init=_init_connection,
    )


async def _run_startup_migrations(pool: Pool) -> None:
    """Run pending schema migrations on startup.

    These are idempotent – safe to run on every boot.
    """
    async with pool.acquire() as conn:
        # Migration: MP -> Lemon Squeezy columns
        has_mp_col = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM information_schema.columns "
            "WHERE table_name='subscriptions' AND column_name='mp_preapproval_id')"
        )
        if has_mp_col:
            print("Running migration: MP -> Lemon Squeezy columns...")
            await conn.execute("""
                ALTER TABLE subscriptions
                    ADD COLUMN IF NOT EXISTS ls_subscription_id TEXT,
                    ADD COLUMN IF NOT EXISTS ls_checkout_id TEXT;
                ALTER TABLE subscriptions
                    DROP COLUMN IF EXISTS mp_preapproval_id,
                    DROP COLUMN IF EXISTS mp_payer_id;
                ALTER TABLE subscription_payments
                    ADD COLUMN IF NOT EXISTS ls_invoice_id TEXT;
                ALTER TABLE subscription_payments
                    DROP COLUMN IF EXISTS mp_payment_id;
                ALTER TABLE subscription_payments
                    ALTER COLUMN currency SET DEFAULT 'USD';
                DROP TABLE IF EXISTS subscription_plans_mp;
            """)
            print("Migration MP -> LS completed.")

        # Ensure LS columns exist (for fresh DBs)
        has_ls_col = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM information_schema.columns "
            "WHERE table_name='subscriptions' AND column_name='ls_subscription_id')"
        )
        if not has_ls_col:
            has_table = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM information_schema.tables "
                "WHERE table_name='subscriptions')"
            )
            if has_table:
                print("Adding LS columns to subscriptions...")
                await conn.execute("""
                    ALTER TABLE subscriptions
                        ADD COLUMN IF NOT EXISTS ls_subscription_id TEXT,
                        ADD COLUMN IF NOT EXISTS ls_checkout_id TEXT;
                    ALTER TABLE subscription_payments
                        ADD COLUMN IF NOT EXISTS ls_invoice_id TEXT;
                """)
                print("LS columns added.")


async def get_pool() -> Pool:
    """Get or create database connection pool."""
    global _pool
    if _pool is None:
        _pool = await create_pool()
        await _run_startup_migrations(_pool)
    return _pool


async def close_pool() -> None:
    """Close database connection pool."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


@asynccontextmanager
async def get_connection() -> AsyncGenerator[asyncpg.Connection, None]:
    """Get database connection from pool."""
    pool = await get_pool()
    async with pool.acquire() as connection:
        yield connection


async def execute_query(query: str, *args) -> str:
    """Execute a query and return status."""
    async with get_connection() as conn:
        return await conn.execute(query, *args)


async def fetch_all(query: str, *args) -> list[asyncpg.Record]:
    """Fetch all rows from a query."""
    async with get_connection() as conn:
        return await conn.fetch(query, *args)


async def fetch_one(query: str, *args) -> asyncpg.Record | None:
    """Fetch one row from a query."""
    async with get_connection() as conn:
        return await conn.fetchrow(query, *args)
