"""Finance repository for database operations."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from ..config.database import get_pool


async def create_expense(
    tenant_id: UUID,
    amount: Decimal,
    category_id: UUID | None = None,
    description: str | None = None,
    expense_date: date | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Create a new expense."""
    pool = await get_pool()
    
    if expense_date is None:
        expense_date = date.today()
    
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO expenses (tenant_id, amount, category_id, description, expense_date, idempotency_key)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id, tenant_id, amount, category_id, description, expense_date, 
                      idempotency_key, created_at
            """,
            tenant_id, amount, category_id, description, expense_date, idempotency_key
        )
        return dict(row)


async def get_expenses(
    tenant_id: UUID,
    start_date: date | None = None,
    end_date: date | None = None,
    category_id: UUID | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Get expenses for a tenant with optional filters."""
    pool = await get_pool()
    
    query = """
        SELECT e.id, e.tenant_id, e.amount, e.category_id, e.description, 
               e.expense_date, e.created_at, e.updated_at,
               bc.name as category_name
        FROM expenses e
        LEFT JOIN budget_categories bc ON e.category_id = bc.id
        WHERE e.tenant_id = $1
    """
    params: list[Any] = [tenant_id]
    param_idx = 2
    
    if start_date:
        query += f" AND e.expense_date >= ${param_idx}"
        params.append(start_date)
        param_idx += 1
    
    if end_date:
        query += f" AND e.expense_date <= ${param_idx}"
        params.append(end_date)
        param_idx += 1
    
    if category_id:
        query += f" AND e.category_id = ${param_idx}"
        params.append(category_id)
        param_idx += 1
    
    query += f" ORDER BY e.expense_date DESC, e.created_at DESC LIMIT ${param_idx} OFFSET ${param_idx + 1}"
    params.extend([limit, offset])
    
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *params)
        return [dict(row) for row in rows]


async def get_expense_by_id(tenant_id: UUID, expense_id: UUID) -> dict[str, Any] | None:
    """Get a single expense by ID."""
    pool = await get_pool()
    
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT e.*, bc.name as category_name
            FROM expenses e
            LEFT JOIN budget_categories bc ON e.category_id = bc.id
            WHERE e.id = $1 AND e.tenant_id = $2
            """,
            expense_id, tenant_id
        )
        return dict(row) if row else None


async def update_expense(
    tenant_id: UUID,
    expense_id: UUID,
    **updates: Any,
) -> dict[str, Any] | None:
    """Update an expense."""
    pool = await get_pool()
    
    # Build SET clause dynamically
    set_parts = []
    params = []
    param_idx = 1
    
    for key, value in updates.items():
        if value is not None:
            set_parts.append(f"{key} = ${param_idx}")
            params.append(value)
            param_idx += 1
    
    if not set_parts:
        return await get_expense_by_id(tenant_id, expense_id)
    
    set_parts.append("updated_at = NOW()")
    params.extend([expense_id, tenant_id])
    
    query = f"""
        UPDATE expenses
        SET {', '.join(set_parts)}
        WHERE id = ${param_idx} AND tenant_id = ${param_idx + 1}
        RETURNING *
    """
    
    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, *params)
        return dict(row) if row else None


async def delete_expense(tenant_id: UUID, expense_id: UUID) -> bool:
    """Delete an expense."""
    pool = await get_pool()
    
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM expenses WHERE id = $1 AND tenant_id = $2",
            expense_id, tenant_id
        )
        return result == "DELETE 1"


async def search_expense(
    tenant_id: UUID,
    amount: Decimal | None = None,
    category_id: UUID | None = None,
    description: str | None = None,
    expense_date: date | None = None,
) -> dict[str, Any] | None:
    """Search for an expense matching criteria. Returns most recent match."""
    pool = await get_pool()
    
    query = """
        SELECT e.id, e.tenant_id, e.amount, e.category_id, e.description, 
               e.expense_date, e.created_at, bc.name as category_name
        FROM expenses e
        LEFT JOIN budget_categories bc ON e.category_id = bc.id
        WHERE e.tenant_id = $1
    """
    params: list[Any] = [tenant_id]
    param_idx = 2
    
    if amount is not None:
        query += f" AND e.amount = ${param_idx}"
        params.append(amount)
        param_idx += 1
    
    if category_id is not None:
        query += f" AND e.category_id = ${param_idx}"
        params.append(category_id)
        param_idx += 1
    
    if description is not None:
        query += f" AND LOWER(e.description) LIKE LOWER(${param_idx})"
        params.append(f"%{description}%")
        param_idx += 1
    
    if expense_date is not None:
        query += f" AND e.expense_date = ${param_idx}"
        params.append(expense_date)
        param_idx += 1
    
    query += " ORDER BY e.created_at DESC LIMIT 1"
    
    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, *params)
        return dict(row) if row else None


# =============================================================================
# BUDGET CATEGORIES
# =============================================================================

async def get_budget_categories(tenant_id: UUID) -> list[dict[str, Any]]:
    """Get all budget categories for a tenant."""
    pool = await get_pool()
    
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, tenant_id, name, monthly_limit, alert_threshold_percent as alert_threshold, created_at
            FROM budget_categories
            WHERE tenant_id = $1
            ORDER BY name
            """,
            tenant_id
        )
        return [dict(row) for row in rows]


async def get_budget_category_by_id(tenant_id: UUID, category_id: UUID) -> dict[str, Any] | None:
    """Get a single budget category by ID."""
    pool = await get_pool()
    
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM budget_categories WHERE id = $1 AND tenant_id = $2",
            category_id, tenant_id
        )
        return dict(row) if row else None


async def get_budget_category_by_name(tenant_id: UUID, name: str) -> dict[str, Any] | None:
    """Get a budget category by name (case-insensitive)."""
    pool = await get_pool()
    
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM budget_categories WHERE tenant_id = $1 AND LOWER(name) = LOWER($2)",
            tenant_id, name
        )
        return dict(row) if row else None


async def create_budget_category(
    tenant_id: UUID,
    name: str,
    monthly_limit: Decimal | None = None,
    alert_threshold: int = 80,
) -> dict[str, Any]:
    """Create a new budget category."""
    pool = await get_pool()
    
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO budget_categories (tenant_id, name, monthly_limit, alert_threshold_percent)
            VALUES ($1, $2, $3, $4)
            RETURNING id, tenant_id, name, monthly_limit, alert_threshold_percent as alert_threshold, created_at
            """,
            tenant_id, name, monthly_limit, alert_threshold
        )
        return dict(row)


async def update_budget_category(
    tenant_id: UUID,
    category_id: UUID,
    **updates: Any,
) -> dict[str, Any] | None:
    """Update a budget category."""
    pool = await get_pool()
    
    set_parts = []
    params = []
    param_idx = 1
    
    for key, value in updates.items():
        if value is not None:
            set_parts.append(f"{key} = ${param_idx}")
            params.append(value)
            param_idx += 1
    
    if not set_parts:
        return await get_budget_category_by_id(tenant_id, category_id)
    
    set_parts.append("updated_at = NOW()")
    params.extend([category_id, tenant_id])
    
    query = f"""
        UPDATE budget_categories
        SET {', '.join(set_parts)}
        WHERE id = ${param_idx} AND tenant_id = ${param_idx + 1}
        RETURNING *
    """
    
    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, *params)
        return dict(row) if row else None


async def delete_budget_category(tenant_id: UUID, category_id: UUID) -> bool:
    """Delete a budget category."""
    pool = await get_pool()
    
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM budget_categories WHERE id = $1 AND tenant_id = $2",
            category_id, tenant_id
        )
        return result == "DELETE 1"


# =============================================================================
# AGGREGATIONS & REPORTS
# =============================================================================

async def get_expenses_summary(
    tenant_id: UUID,
    start_date: date,
    end_date: date,
    category_id: UUID | None = None,
) -> dict[str, Any]:
    """Get expense summary for a period."""
    pool = await get_pool()
    
    query = """
        SELECT 
            COALESCE(SUM(amount), 0) as total,
            COUNT(*) as count
        FROM expenses
        WHERE tenant_id = $1 AND expense_date >= $2 AND expense_date <= $3
    """
    params: list[Any] = [tenant_id, start_date, end_date]
    
    if category_id:
        query += " AND category_id = $4"
        params.append(category_id)
    
    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, *params)
        return {
            "total": row["total"] or Decimal("0"),
            "count": row["count"] or 0,
        }


async def get_expenses_by_category(
    tenant_id: UUID,
    start_date: date,
    end_date: date,
) -> list[dict[str, Any]]:
    """Get expenses grouped by category."""
    pool = await get_pool()
    
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT 
                e.category_id,
                COALESCE(bc.name, 'Sin categoría') as category_name,
                SUM(e.amount) as total,
                COUNT(*) as count
            FROM expenses e
            LEFT JOIN budget_categories bc ON e.category_id = bc.id
            WHERE e.tenant_id = $1 AND e.expense_date >= $2 AND e.expense_date <= $3
            GROUP BY e.category_id, bc.name
            ORDER BY total DESC
            """,
            tenant_id, start_date, end_date
        )
        return [dict(row) for row in rows]


async def get_daily_expenses(
    tenant_id: UUID,
    start_date: date,
    end_date: date,
) -> list[dict[str, Any]]:
    """Get daily expense totals."""
    pool = await get_pool()
    
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT 
                expense_date as date,
                SUM(amount) as amount
            FROM expenses
            WHERE tenant_id = $1 AND expense_date >= $2 AND expense_date <= $3
            GROUP BY expense_date
            ORDER BY expense_date
            """,
            tenant_id, start_date, end_date
        )
        return [dict(row) for row in rows]


async def get_monthly_spending_by_category(
    tenant_id: UUID,
    year: int,
    month: int,
) -> list[dict[str, Any]]:
    """Get current month spending per category."""
    pool = await get_pool()
    
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT 
                bc.id as category_id,
                bc.name,
                bc.monthly_limit,
                bc.alert_threshold_percent as alert_threshold,
                COALESCE(SUM(e.amount), 0) as current_spending
            FROM budget_categories bc
            LEFT JOIN expenses e ON bc.id = e.category_id 
                AND EXTRACT(YEAR FROM e.expense_date) = $2
                AND EXTRACT(MONTH FROM e.expense_date) = $3
            WHERE bc.tenant_id = $1
            GROUP BY bc.id, bc.name, bc.monthly_limit, bc.alert_threshold_percent
            ORDER BY bc.name
            """,
            tenant_id, year, month
        )
        return [dict(row) for row in rows]
