"""Finance service for business logic."""

from datetime import date, timedelta
from decimal import Decimal
from typing import Literal
from uuid import UUID

from ..repositories import finance as repo
from ..schemas.finance import (
    AgentBudgetStatus,
    AgentGetBudgetResponse,
    AgentGetReportResponse,
    AgentLogExpenseResponse,
    BudgetAlert,
    BudgetCategoryResponse,
    CategorySummary,
    ExpenseResponse,
    ReportSummary,
    TrendDataPoint,
)


def _get_period_dates(period: Literal["day", "week", "month", "year"]) -> tuple[date, date]:
    """Get start and end dates for a period."""
    today = date.today()
    
    if period == "day":
        return today, today
    elif period == "week":
        start = today - timedelta(days=today.weekday())
        return start, today
    elif period == "month":
        start = today.replace(day=1)
        return start, today
    elif period == "year":
        start = today.replace(month=1, day=1)
        return start, today
    
    return today, today


def _get_alert_level(percentage: float, threshold: int) -> Literal["ok", "warning", "critical", "exceeded"]:
    """Determine alert level based on percentage used."""
    if percentage >= 100:
        return "exceeded"
    elif percentage >= 95:
        return "critical"
    elif percentage >= threshold:
        return "warning"
    return "ok"


async def resolve_category(tenant_id: UUID, category_name: str) -> UUID:
    """Resolve category name to ID, creating if necessary."""
    # Try to find existing category
    category = await repo.get_budget_category_by_name(tenant_id, category_name)
    
    if category:
        return category["id"]
    
    # Create new category with no limit (user can set later)
    new_category = await repo.create_budget_category(
        tenant_id=tenant_id,
        name=category_name.title(),
        monthly_limit=None,
        alert_threshold=80,
    )
    
    return new_category["id"]


async def create_expense_with_alert(
    tenant_id: UUID,
    amount: Decimal,
    category_name: str,
    description: str | None = None,
    expense_date: date | None = None,
) -> AgentLogExpenseResponse:
    """Create expense and check for budget alerts."""
    # Resolve category
    category_id = await resolve_category(tenant_id, category_name)
    
    # Create expense
    expense = await repo.create_expense(
        tenant_id=tenant_id,
        amount=amount,
        category_id=category_id,
        description=description,
        expense_date=expense_date or date.today(),
    )
    
    # Check budget alert
    alert = await check_category_alert(tenant_id, category_id)
    
    # Build response message
    if alert:
        if alert.alert_level == "exceeded":
            message = f"⚠️ Gasto registrado. ¡PRESUPUESTO EXCEDIDO en {category_name}! ({alert.percentage_used:.0f}%)"
        elif alert.alert_level == "critical":
            message = f"⚠️ Gasto registrado. ¡Alerta crítica en {category_name}! ({alert.percentage_used:.0f}%)"
        else:
            message = f"✅ Gasto registrado. Atención: {category_name} al {alert.percentage_used:.0f}%"
    else:
        message = f"✅ Gasto de ${amount:,.0f} registrado en {category_name}"
    
    return AgentLogExpenseResponse(
        success=True,
        expense_id=expense["id"],
        message=message,
        alert=alert,
    )


async def check_category_alert(tenant_id: UUID, category_id: UUID) -> BudgetAlert | None:
    """Check if a category has exceeded its alert threshold."""
    category = await repo.get_budget_category_by_id(tenant_id, category_id)
    
    if not category or not category.get("monthly_limit"):
        return None
    
    today = date.today()
    spending_data = await repo.get_monthly_spending_by_category(
        tenant_id, today.year, today.month
    )
    
    cat_spending = next(
        (s for s in spending_data if s["category_id"] == category_id),
        None
    )
    
    if not cat_spending:
        return None
    
    current = Decimal(str(cat_spending["current_spending"]))
    limit = Decimal(str(category["monthly_limit"]))
    threshold = category.get("alert_threshold", 80)
    
    if limit <= 0:
        return None
    
    percentage = float(current / limit * 100)
    
    if percentage < threshold:
        return None
    
    return BudgetAlert(
        category_id=category_id,
        category_name=category["name"],
        monthly_limit=limit,
        current_spending=current,
        percentage_used=percentage,
        alert_level=_get_alert_level(percentage, threshold),
    )


async def get_report_for_agent(
    tenant_id: UUID,
    period: Literal["day", "week", "month", "year"] = "month",
    category_name: str | None = None,
) -> AgentGetReportResponse:
    """Get simplified report for agent."""
    start_date, end_date = _get_period_dates(period)
    
    category_id = None
    if category_name:
        cat = await repo.get_budget_category_by_name(tenant_id, category_name)
        if cat:
            category_id = cat["id"]
    
    # Get summary
    summary = await repo.get_expenses_summary(tenant_id, start_date, end_date, category_id)
    
    # Get by category
    by_category_data = await repo.get_expenses_by_category(tenant_id, start_date, end_date)
    
    total = Decimal(str(summary["total"]))
    count = summary["count"]
    days = (end_date - start_date).days + 1
    daily_avg = total / days if days > 0 else Decimal("0")
    
    # Build category summaries
    by_category = []
    for cat in by_category_data:
        cat_total = Decimal(str(cat["total"]))
        pct = float(cat_total / total * 100) if total > 0 else 0
        by_category.append(CategorySummary(
            category_id=cat["category_id"],
            category_name=cat["category_name"],
            total=cat_total,
            count=cat["count"],
            percentage=pct,
        ))
    
    top_category = by_category[0].category_name if by_category else None
    
    period_names = {
        "day": "Hoy",
        "week": "Esta semana",
        "month": "Este mes",
        "year": "Este año",
    }
    
    return AgentGetReportResponse(
        period=period_names.get(period, period),
        total_spent=total,
        transaction_count=count,
        by_category=by_category,
        top_category=top_category,
        daily_average=daily_avg.quantize(Decimal("0.01")),
    )


async def get_budget_for_agent(
    tenant_id: UUID,
    category_name: str | None = None,
) -> AgentGetBudgetResponse:
    """Get budget status for agent."""
    today = date.today()
    spending_data = await repo.get_monthly_spending_by_category(
        tenant_id, today.year, today.month
    )
    
    budgets = []
    alerts = []
    
    for cat in spending_data:
        if category_name and cat["name"].lower() != category_name.lower():
            continue
        
        limit = Decimal(str(cat["monthly_limit"])) if cat["monthly_limit"] else None
        spent = Decimal(str(cat["current_spending"]))
        remaining = limit - spent if limit else None
        percentage = float(spent / limit * 100) if limit and limit > 0 else 0
        threshold = cat.get("alert_threshold", 80)
        status = _get_alert_level(percentage, threshold)
        
        budgets.append(AgentBudgetStatus(
            category=cat["name"],
            limit=limit,
            spent=spent,
            remaining=remaining,
            percentage=percentage,
            status=status,
        ))
        
        if status in ("warning", "critical", "exceeded"):
            if status == "exceeded":
                alerts.append(f"🚨 {cat['name']}: EXCEDIDO ({percentage:.0f}%)")
            elif status == "critical":
                alerts.append(f"⚠️ {cat['name']}: Crítico ({percentage:.0f}%)")
            else:
                alerts.append(f"📊 {cat['name']}: Atención ({percentage:.0f}%)")
    
    return AgentGetBudgetResponse(budgets=budgets, alerts=alerts)


async def get_full_report(
    tenant_id: UUID,
    start_date: date,
    end_date: date,
) -> ReportSummary:
    """Get full report for dashboard."""
    summary = await repo.get_expenses_summary(tenant_id, start_date, end_date)
    by_category_data = await repo.get_expenses_by_category(tenant_id, start_date, end_date)
    daily_data = await repo.get_daily_expenses(tenant_id, start_date, end_date)
    
    total = Decimal(str(summary["total"]))
    count = summary["count"]
    days = (end_date - start_date).days + 1
    daily_avg = total / days if days > 0 else Decimal("0")
    
    by_category = []
    for cat in by_category_data:
        cat_total = Decimal(str(cat["total"]))
        pct = float(cat_total / total * 100) if total > 0 else 0
        by_category.append(CategorySummary(
            category_id=cat["category_id"],
            category_name=cat["category_name"],
            total=cat_total,
            count=cat["count"],
            percentage=pct,
        ))
    
    daily_trend = [
        TrendDataPoint(date=str(d["date"]), amount=Decimal(str(d["amount"])))
        for d in daily_data
    ]
    
    return ReportSummary(
        period="custom",
        start_date=start_date,
        end_date=end_date,
        total_spent=total,
        transaction_count=count,
        daily_average=daily_avg.quantize(Decimal("0.01")),
        by_category=by_category,
        daily_trend=daily_trend,
    )


async def get_budgets_with_spending(tenant_id: UUID) -> list[BudgetCategoryResponse]:
    """Get all budgets with current spending calculated."""
    today = date.today()
    spending_data = await repo.get_monthly_spending_by_category(
        tenant_id, today.year, today.month
    )
    
    result = []
    for cat in spending_data:
        limit = Decimal(str(cat["monthly_limit"])) if cat["monthly_limit"] else None
        spent = Decimal(str(cat["current_spending"]))
        remaining = limit - spent if limit else None
        percentage = float(spent / limit * 100) if limit and limit > 0 else 0
        
        result.append(BudgetCategoryResponse(
            id=cat["category_id"],
            tenant_id=tenant_id,
            name=cat["name"],
            monthly_limit=limit,
            alert_threshold=cat.get("alert_threshold", 80),
            current_spending=spent,
            remaining=remaining,
            percentage_used=percentage,
            created_at=None,
            updated_at=None,
        ))
    
    return result


async def delete_expense_for_agent(
    tenant_id: UUID,
    amount: Decimal | None = None,
    category_name: str | None = None,
    description: str | None = None,
    expense_date: date | None = None,
) -> dict:
    """Delete an expense matching the given criteria."""
    from ..schemas.finance import AgentDeleteExpenseResponse
    
    # Resolve category if provided
    category_id = None
    if category_name:
        cat = await repo.get_budget_category_by_name(tenant_id, category_name)
        if cat:
            category_id = cat["id"]
    
    # Default to today if no date provided
    if expense_date is None:
        expense_date = date.today()
    
    # Search for matching expense
    expense = await repo.search_expense(
        tenant_id=tenant_id,
        amount=amount,
        category_id=category_id,
        description=description,
        expense_date=expense_date,
    )
    
    if not expense:
        return AgentDeleteExpenseResponse(
            success=False,
            message="❌ No se encontró ningún gasto que coincida con los criterios",
            deleted_expense=None,
        ).model_dump()
    
    # Delete the expense
    deleted = await repo.delete_expense(tenant_id, expense["id"])
    
    if deleted:
        cat_name = expense.get("category_name", "Sin categoría")
        return AgentDeleteExpenseResponse(
            success=True,
            message=f"🗑️ Gasto eliminado: ${expense['amount']:,.0f} en {cat_name} ({expense['expense_date']})",
            deleted_expense={
                "id": str(expense["id"]),
                "amount": float(expense["amount"]),
                "category": cat_name,
                "description": expense.get("description"),
                "date": str(expense["expense_date"]),
            },
        ).model_dump()
    
    return AgentDeleteExpenseResponse(
        success=False,
        message="❌ Error al eliminar el gasto",
        deleted_expense=None,
    ).model_dump()


async def modify_expense_for_agent(
    tenant_id: UUID,
    search_amount: Decimal | None = None,
    search_category: str | None = None,
    search_description: str | None = None,
    search_date: date | None = None,
    new_amount: Decimal | None = None,
    new_category: str | None = None,
    new_description: str | None = None,
) -> dict:
    """Modify an expense matching the given criteria."""
    from ..schemas.finance import AgentModifyExpenseResponse
    
    # Resolve search category if provided
    search_category_id = None
    if search_category:
        cat = await repo.get_budget_category_by_name(tenant_id, search_category)
        if cat:
            search_category_id = cat["id"]
    
    # Default to today if no date provided
    if search_date is None:
        search_date = date.today()
    
    # Search for matching expense
    expense = await repo.search_expense(
        tenant_id=tenant_id,
        amount=search_amount,
        category_id=search_category_id,
        description=search_description,
        expense_date=search_date,
    )
    
    if not expense:
        return AgentModifyExpenseResponse(
            success=False,
            message="❌ No se encontró ningún gasto que coincida con los criterios",
            modified_expense=None,
        ).model_dump()
    
    # Build updates
    updates = {}
    if new_amount is not None:
        updates["amount"] = new_amount
    if new_description is not None:
        updates["description"] = new_description
    if new_category is not None:
        new_cat = await repo.get_budget_category_by_name(tenant_id, new_category)
        if new_cat:
            updates["category_id"] = new_cat["id"]
        else:
            # Create new category
            new_category_id = await resolve_category(tenant_id, new_category)
            updates["category_id"] = new_category_id
    
    if not updates:
        return AgentModifyExpenseResponse(
            success=False,
            message="❌ No se especificaron cambios para realizar",
            modified_expense=None,
        ).model_dump()
    
    # Update the expense
    updated = await repo.update_expense(tenant_id, expense["id"], **updates)
    
    if updated:
        # Get updated expense with category name
        updated_expense = await repo.get_expense_by_id(tenant_id, expense["id"])
        cat_name = updated_expense.get("category_name", "Sin categoría") if updated_expense else "Sin categoría"
        
        return AgentModifyExpenseResponse(
            success=True,
            message=f"✏️ Gasto modificado: ${updated['amount']:,.0f} en {cat_name}",
            modified_expense={
                "id": str(updated["id"]),
                "amount": float(updated["amount"]),
                "category": cat_name,
                "description": updated.get("description"),
                "date": str(updated["expense_date"]),
            },
        ).model_dump()
    
    return AgentModifyExpenseResponse(
        success=False,
        message="❌ Error al modificar el gasto",
        modified_expense=None,
    ).model_dump()


async def set_budget_for_agent(
    tenant_id: UUID,
    category_name: str,
    monthly_limit: Decimal,
    alert_threshold: int = 80,
) -> dict:
    """Set or update a budget for a category.
    
    If the category exists, updates the monthly limit.
    If the category doesn't exist, creates it with the specified limit.
    """
    # Check if category exists
    category = await repo.get_budget_category_by_name(tenant_id, category_name)
    
    if category:
        # Update existing category
        updated = await repo.update_budget_category(
            tenant_id=tenant_id,
            category_id=category["id"],
            monthly_limit=monthly_limit,
            alert_threshold_percent=alert_threshold,
        )
        
        return {
            "success": True,
            "message": f"💰 Presupuesto de {category_name} actualizado a ${monthly_limit:,.0f}/mes",
            "budget": {
                "id": str(updated["id"]) if updated else None,
                "category": category_name,
                "monthly_limit": float(monthly_limit),
                "alert_threshold": alert_threshold,
            },
            "created": False,
        }
    else:
        # Create new category with limit
        new_category = await repo.create_budget_category(
            tenant_id=tenant_id,
            name=category_name.title(),
            monthly_limit=monthly_limit,
            alert_threshold=alert_threshold,
        )
        
        return {
            "success": True,
            "message": f"💰 Presupuesto creado: {category_name.title()} con ${monthly_limit:,.0f}/mes",
            "budget": {
                "id": str(new_category["id"]),
                "category": new_category["name"],
                "monthly_limit": float(monthly_limit),
                "alert_threshold": alert_threshold,
            },
            "created": True,
        }


async def delete_expenses_bulk_for_agent(
    tenant_id: UUID,
    period: str | None = None,
    category_name: str | None = None,
    confirm: bool = False,
) -> dict:
    """Delete multiple expenses for the agent."""
    
    if not confirm:
        return {
            "success": False,
            "message": "⚠️ Para eliminar gastos, necesito confirmación. Decime 'confirmo' o 'sí, eliminar'.",
            "deleted_count": 0,
        }
    
    # Determine date range based on period
    today = date.today()
    start_date = None
    end_date = None
    delete_all = False
    
    if period == "today" or period == "hoy":
        start_date = today
        end_date = today
    elif period == "week" or period == "semana":
        start_date = today - timedelta(days=today.weekday())
        end_date = today
    elif period == "month" or period == "mes":
        start_date = today.replace(day=1)
        end_date = today
    elif period == "year" or period == "año":
        start_date = today.replace(month=1, day=1)
        end_date = today
    elif period == "all" or period == "todos" or period == "todo":
        delete_all = True
    
    # Resolve category
    category_id = None
    if category_name:
        cat = await repo.get_budget_category_by_name(tenant_id, category_name)
        if cat:
            category_id = cat["id"]
    
    # Perform bulk delete
    deleted_count = await repo.delete_expenses_bulk(
        tenant_id=tenant_id,
        start_date=start_date,
        end_date=end_date,
        category_id=category_id,
        delete_all=delete_all,
    )
    
    if deleted_count > 0:
        period_text = period or "seleccionado"
        cat_text = f" de {category_name}" if category_name else ""
        return {
            "success": True,
            "message": f"🗑️ Se eliminaron {deleted_count} gasto(s){cat_text} del período {period_text}.",
            "deleted_count": deleted_count,
        }
    
    return {
        "success": False,
        "message": "❌ No se encontraron gastos que coincidan con los criterios.",
        "deleted_count": 0,
    }
