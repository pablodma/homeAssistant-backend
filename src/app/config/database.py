"""Database connection management."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import asyncpg
from asyncpg import Pool

from .settings import get_settings

# Global connection pool
_pool: Pool | None = None


async def create_pool() -> Pool:
    """Create database connection pool."""
    settings = get_settings()
    return await asyncpg.create_pool(
        dsn=settings.database_url,
        min_size=2,
        max_size=10,
        command_timeout=60,
    )


async def get_pool() -> Pool:
    """Get or create database connection pool."""
    global _pool
    if _pool is None:
        _pool = await create_pool()
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
