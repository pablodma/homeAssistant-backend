"""Finance API endpoints."""

from datetime import date
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..middleware.auth import get_current_user, validate_tenant_access
from ..repositories import finance as repo
from ..schemas.auth import CurrentUser
from ..schemas.finance import (
    AgentDeleteExpenseRequest,
    AgentDeleteExpenseResponse,
    AgentGetBudgetRequest,
    AgentGetBudgetResponse,
    AgentGetReportRequest,
    AgentGetReportResponse,
    AgentListCategoriesResponse,
    AgentLogExpenseRequest,
    AgentLogExpenseResponse,
    AgentModifyExpenseRequest,
    AgentModifyExpenseResponse,
    AgentSetBudgetRequest,
    AgentSetBudgetResponse,
    BudgetCategoryCreate,
    BudgetCategoryResponse,
    BudgetCategoryUpdate,
    ExpenseCreate,
    ExpenseResponse,
    ExpenseUpdate,
    ReportSummary,
)
from ..services import finance as finance_service

router = APIRouter(prefix="/tenants/{tenant_id}", tags=["Finance"])


# =============================================================================
# AGENT ENDPOINTS (for n8n)
# =============================================================================

@router.post("/agent/expense", response_model=AgentLogExpenseResponse)
async def agent_log_expense(
    tenant_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    _: Annotated[None, Depends(validate_tenant_access)],
    amount: Decimal = Query(..., description="Expense amount"),
    category: str = Query(..., description="Category name"),
    description: str | None = Query(None, description="Optional description"),
    expense_date: date | None = Query(None, description="Expense date YYYY-MM-DD"),
) -> AgentLogExpenseResponse:
    """
    Log an expense from the n8n agent.
    
    Creates the expense and returns budget alerts if applicable.
    """
    return await finance_service.create_expense_with_alert(
        tenant_id=tenant_id,
        amount=amount,
        category_name=category,
        description=description,
        expense_date=expense_date,
    )


@router.get("/agent/report", response_model=AgentGetReportResponse)
async def agent_get_report(
    tenant_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    _: Annotated[None, Depends(validate_tenant_access)],
    period: str = Query("month", pattern="^(day|week|month|year)$"),
    category: str | None = Query(None),
) -> AgentGetReportResponse:
    """
    Get expense report for the n8n agent.
    
    Returns simplified report data suitable for WhatsApp responses.
    """
    return await finance_service.get_report_for_agent(
        tenant_id=tenant_id,
        period=period,  # type: ignore
        category_name=category,
    )


@router.get("/agent/budget", response_model=AgentGetBudgetResponse)
async def agent_get_budget(
    tenant_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    _: Annotated[None, Depends(validate_tenant_access)],
    category: str | None = Query(None),
) -> AgentGetBudgetResponse:
    """
    Get budget status for the n8n agent.
    
    Returns current spending vs limits for all or specific categories.
    """
    return await finance_service.get_budget_for_agent(
        tenant_id=tenant_id,
        category_name=category,
    )


@router.put("/agent/budget", response_model=AgentSetBudgetResponse)
async def agent_set_budget(
    tenant_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    _: Annotated[None, Depends(validate_tenant_access)],
    category: str = Query(..., description="Category name"),
    monthly_limit: Decimal = Query(..., gt=0, description="Monthly budget limit"),
    alert_threshold: int = Query(80, ge=0, le=100, description="Alert threshold percentage"),
) -> AgentSetBudgetResponse:
    """
    Set or update a budget for a category from the n8n agent.
    
    If the category exists, updates the monthly limit.
    If the category doesn't exist, creates it with the specified limit.
    """
    result = await finance_service.set_budget_for_agent(
        tenant_id=tenant_id,
        category_name=category,
        monthly_limit=monthly_limit,
        alert_threshold=alert_threshold,
    )
    return AgentSetBudgetResponse(**result)


@router.get("/agent/categories", response_model=AgentListCategoriesResponse)
async def agent_list_categories(
    tenant_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    _: Annotated[None, Depends(validate_tenant_access)],
) -> AgentListCategoriesResponse:
    """
    List all budget categories for the agent.
    
    Used to show category options to user when registering an expense
    with an unknown category.
    """
    return await finance_service.list_categories_for_agent(tenant_id)


@router.delete("/agent/expense", response_model=AgentDeleteExpenseResponse)
async def agent_delete_expense(
    tenant_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    _: Annotated[None, Depends(validate_tenant_access)],
    amount: Decimal | None = Query(None, description="Amount to match"),
    category: str | None = Query(None, description="Category to match"),
    description: str | None = Query(None, description="Description to match"),
    expense_date: date | None = Query(None, description="Date to match"),
) -> AgentDeleteExpenseResponse:
    """
    Delete an expense from the n8n agent.
    
    Searches for a matching expense and deletes it.
    """
    result = await finance_service.delete_expense_for_agent(
        tenant_id=tenant_id,
        amount=amount,
        category_name=category,
        description=description,
        expense_date=expense_date,
    )
    return AgentDeleteExpenseResponse(**result)


@router.delete("/agent/expenses/bulk")
async def agent_delete_expenses_bulk(
    tenant_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    _: Annotated[None, Depends(validate_tenant_access)],
    period: str | None = Query(None, description="Period: today, week, month, year, all"),
    category: str | None = Query(None, description="Category to filter"),
    confirm: bool = Query(False, description="Must be true to confirm deletion"),
) -> dict:
    """
    Delete multiple expenses from the n8n agent.
    
    Period options:
    - today/hoy: expenses from today
    - week/semana: expenses from this week
    - month/mes: expenses from this month
    - year/año: expenses from this year
    - all/todos/todo: ALL expenses (requires confirm=true)
    """
    result = await finance_service.delete_expenses_bulk_for_agent(
        tenant_id=tenant_id,
        period=period,
        category_name=category,
        confirm=confirm,
    )
    return result


@router.patch("/agent/expense", response_model=AgentModifyExpenseResponse)
async def agent_modify_expense(
    tenant_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    _: Annotated[None, Depends(validate_tenant_access)],
    # Search criteria
    search_amount: Decimal | None = Query(None, description="Amount to search for"),
    search_category: str | None = Query(None, description="Category to search for"),
    search_description: str | None = Query(None, description="Description to search for"),
    search_date: date | None = Query(None, description="Date to search for"),
    # New values
    new_amount: Decimal | None = Query(None, description="New amount"),
    new_category: str | None = Query(None, description="New category"),
    new_description: str | None = Query(None, description="New description"),
) -> AgentModifyExpenseResponse:
    """
    Modify an expense from the n8n agent.
    
    Searches for a matching expense and updates it.
    """
    result = await finance_service.modify_expense_for_agent(
        tenant_id=tenant_id,
        search_amount=search_amount,
        search_category=search_category,
        search_description=search_description,
        search_date=search_date,
        new_amount=new_amount,
        new_category=new_category,
        new_description=new_description,
    )
    return AgentModifyExpenseResponse(**result)


# =============================================================================
# EXPENSE CRUD ENDPOINTS (for dashboard)
# =============================================================================

@router.get("/expenses", response_model=list[ExpenseResponse])
async def list_expenses(
    tenant_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    _: Annotated[None, Depends(validate_tenant_access)],
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    category_id: UUID | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> list[ExpenseResponse]:
    """List expenses with optional filters."""
    expenses = await repo.get_expenses(
        tenant_id=tenant_id,
        start_date=start_date,
        end_date=end_date,
        category_id=category_id,
        limit=limit,
        offset=offset,
    )
    return [ExpenseResponse(**e) for e in expenses]


@router.post("/expenses", response_model=ExpenseResponse, status_code=status.HTTP_201_CREATED)
async def create_expense(
    tenant_id: UUID,
    expense: ExpenseCreate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    _: Annotated[None, Depends(validate_tenant_access)],
) -> ExpenseResponse:
    """Create a new expense."""
    result = await repo.create_expense(
        tenant_id=tenant_id,
        amount=expense.amount,
        category_id=expense.category_id,
        description=expense.description,
        expense_date=expense.expense_date or date.today(),
        idempotency_key=expense.idempotency_key,
    )
    return ExpenseResponse(**result)


@router.get("/expenses/{expense_id}", response_model=ExpenseResponse)
async def get_expense(
    tenant_id: UUID,
    expense_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    _: Annotated[None, Depends(validate_tenant_access)],
) -> ExpenseResponse:
    """Get a single expense."""
    expense = await repo.get_expense_by_id(tenant_id, expense_id)
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    return ExpenseResponse(**expense)


@router.patch("/expenses/{expense_id}", response_model=ExpenseResponse)
async def update_expense(
    tenant_id: UUID,
    expense_id: UUID,
    expense: ExpenseUpdate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    _: Annotated[None, Depends(validate_tenant_access)],
) -> ExpenseResponse:
    """Update an expense."""
    updates = expense.model_dump(exclude_unset=True)
    result = await repo.update_expense(tenant_id, expense_id, **updates)
    if not result:
        raise HTTPException(status_code=404, detail="Expense not found")
    return ExpenseResponse(**result)


@router.delete("/expenses/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_expense(
    tenant_id: UUID,
    expense_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    _: Annotated[None, Depends(validate_tenant_access)],
) -> None:
    """Delete an expense."""
    deleted = await repo.delete_expense(tenant_id, expense_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Expense not found")


# =============================================================================
# BUDGET CATEGORY ENDPOINTS
# =============================================================================

@router.get("/budgets", response_model=list[BudgetCategoryResponse])
async def list_budgets(
    tenant_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    _: Annotated[None, Depends(validate_tenant_access)],
) -> list[BudgetCategoryResponse]:
    """List all budget categories with current spending."""
    return await finance_service.get_budgets_with_spending(tenant_id)


@router.post("/budgets", response_model=BudgetCategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_budget(
    tenant_id: UUID,
    budget: BudgetCategoryCreate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    _: Annotated[None, Depends(validate_tenant_access)],
) -> BudgetCategoryResponse:
    """Create a new budget category."""
    result = await repo.create_budget_category(
        tenant_id=tenant_id,
        name=budget.name,
        monthly_limit=budget.monthly_limit,
        alert_threshold=budget.alert_threshold,
    )
    return BudgetCategoryResponse(
        **result,
        current_spending=Decimal("0"),
        remaining=budget.monthly_limit,
        percentage_used=0.0,
    )


@router.patch("/budgets/{budget_id}", response_model=BudgetCategoryResponse)
async def update_budget(
    tenant_id: UUID,
    budget_id: UUID,
    budget: BudgetCategoryUpdate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    _: Annotated[None, Depends(validate_tenant_access)],
) -> BudgetCategoryResponse:
    """Update a budget category."""
    updates = budget.model_dump(exclude_unset=True)
    result = await repo.update_budget_category(tenant_id, budget_id, **updates)
    if not result:
        raise HTTPException(status_code=404, detail="Budget category not found")
    
    # Get updated with spending
    budgets = await finance_service.get_budgets_with_spending(tenant_id)
    updated = next((b for b in budgets if b.id == budget_id), None)
    if not updated:
        raise HTTPException(status_code=404, detail="Budget category not found")
    return updated


@router.delete("/budgets/{budget_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_budget(
    tenant_id: UUID,
    budget_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    _: Annotated[None, Depends(validate_tenant_access)],
) -> None:
    """Delete a budget category."""
    deleted = await repo.delete_budget_category(tenant_id, budget_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Budget category not found")


# =============================================================================
# REPORT ENDPOINTS
# =============================================================================

@router.get("/reports/summary", response_model=ReportSummary)
async def get_report_summary(
    tenant_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    _: Annotated[None, Depends(validate_tenant_access)],
    start_date: date = Query(...),
    end_date: date = Query(...),
) -> ReportSummary:
    """Get detailed expense report for dashboard."""
    return await finance_service.get_full_report(tenant_id, start_date, end_date)
