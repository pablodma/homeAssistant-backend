"""Finance schemas for expenses, budgets, and reports."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import Field

from .common import BaseSchema, TimestampMixin


# =============================================================================
# EXPENSE SCHEMAS
# =============================================================================

class ExpenseBase(BaseSchema):
    """Base expense schema."""
    
    amount: Decimal = Field(..., gt=0, description="Expense amount")
    category_id: UUID | None = Field(None, description="Budget category ID")
    category_name: str | None = Field(None, description="Category name (for display)")
    description: str | None = Field(None, max_length=500)
    expense_date: date = Field(default_factory=date.today)


class ExpenseCreate(BaseSchema):
    """Schema for creating an expense."""
    
    amount: Decimal = Field(..., gt=0)
    category_id: UUID | None = None
    category_name: str | None = None
    description: str | None = None
    expense_date: date | None = None
    idempotency_key: str | None = None


class ExpenseUpdate(BaseSchema):
    """Schema for updating an expense."""
    
    amount: Decimal | None = Field(None, gt=0)
    category_id: UUID | None = None
    description: str | None = None
    expense_date: date | None = None


class ExpenseResponse(ExpenseBase, TimestampMixin):
    """Expense response schema."""
    
    id: UUID
    tenant_id: UUID


# =============================================================================
# INCOME SCHEMAS
# =============================================================================

class IncomeBase(BaseSchema):
    """Base income schema."""
    amount: Decimal = Field(..., gt=0, description="Income amount")
    description: str | None = Field(None, max_length=500)
    income_date: date = Field(default_factory=date.today)


class IncomeCreate(BaseSchema):
    """Schema for creating an income."""
    amount: Decimal = Field(..., gt=0)
    description: str | None = None
    income_date: date | None = None
    idempotency_key: str | None = None


class IncomeUpdate(BaseSchema):
    """Schema for updating an income."""
    amount: Decimal | None = Field(None, gt=0)
    description: str | None = None
    income_date: date | None = None


class IncomeResponse(IncomeBase, TimestampMixin):
    """Income response schema."""
    id: UUID
    tenant_id: UUID


# =============================================================================
# BUDGET CATEGORY SCHEMAS
# =============================================================================

class BudgetCategoryBase(BaseSchema):
    """Base budget category schema."""
    
    name: str = Field(..., min_length=1, max_length=100)
    monthly_limit: Decimal | None = Field(None, ge=0)
    alert_threshold: int = Field(default=80, ge=0, le=100)


class BudgetCategoryCreate(BudgetCategoryBase):
    """Schema for creating a budget category."""
    pass


class BudgetCategoryUpdate(BaseSchema):
    """Schema for updating a budget category."""
    
    name: str | None = Field(None, min_length=1, max_length=100)
    monthly_limit: Decimal | None = Field(None, ge=0)
    alert_threshold: int | None = Field(None, ge=0, le=100)


class BudgetCategoryResponse(BudgetCategoryBase):
    """Budget category response schema."""
    
    id: UUID
    tenant_id: UUID
    current_spending: Decimal = Decimal("0")
    remaining: Decimal | None = None
    percentage_used: float = 0.0
    created_at: datetime | None = None
    updated_at: datetime | None = None


class BudgetGroupUpdate(BaseSchema):
    """Schema for updating a budget group's monthly limit."""
    monthly_limit: Decimal | None = Field(None, ge=0)


class SubcategorySpending(BaseSchema):
    """Spending info for a single subcategory within an overview."""
    id: UUID
    name: str
    total_spent: Decimal = Decimal("0")
    count: int = 0


class BudgetGroupOverview(BaseSchema):
    """A budget group with aggregated spending and subcategories."""
    id: UUID
    name: str
    monthly_limit: Decimal | None = None
    total_spent: Decimal = Decimal("0")
    remaining: Decimal | None = None
    percentage_used: float = 0.0
    subcategories: list[SubcategorySpending] = []


class FinanceOverviewResponse(BaseSchema):
    """Response for the monthly finance overview endpoint."""
    month: str = Field(..., description="YYYY-MM")
    total_income: Decimal = Decimal("0")
    total_expense: Decimal = Decimal("0")
    balance: Decimal = Decimal("0")
    comparison_previous_month: float | None = None
    groups: list[BudgetGroupOverview] = []


# =============================================================================
# REPORT SCHEMAS
# =============================================================================

class CategorySummary(BaseSchema):
    """Summary of spending by category."""
    
    category_id: UUID | None
    category_name: str
    total: Decimal
    count: int
    percentage: float = 0.0


class TrendDataPoint(BaseSchema):
    """Single data point for trend charts."""
    
    date: str
    amount: Decimal


class ReportSummary(BaseSchema):
    """Complete report summary."""
    
    period: str
    start_date: date
    end_date: date
    total_spent: Decimal
    transaction_count: int
    daily_average: Decimal
    by_category: list[CategorySummary]
    daily_trend: list[TrendDataPoint]
    comparison_previous: float | None = None


class TrendReport(BaseSchema):
    """Trend report over time."""
    
    period: Literal["daily", "weekly", "monthly"]
    data: list[TrendDataPoint]


class MonthlyCategoryPoint(BaseSchema):
    """Single data point for monthly-by-category charts (month + category + total)."""

    month: str = Field(..., description="Month as YYYY-MM")
    category_id: UUID | None
    category_name: str = Field(..., description="Category name (or 'Sin categoría')")
    total: Decimal = Field(default=Decimal("0"))


class MonthlyByCategoryResponse(BaseSchema):
    """Response for GET /reports/monthly-by-category: evolution by month and category."""

    months: list[str] = Field(..., description="Ordered list of month keys (YYYY-MM)")
    data: list[MonthlyCategoryPoint] = Field(
        ..., description="One row per (month, category) with total spent"
    )


# =============================================================================
# BUDGET ALERT SCHEMAS
# =============================================================================

class BudgetAlert(BaseSchema):
    """Budget alert when threshold is exceeded."""
    
    category_id: UUID
    category_name: str
    monthly_limit: Decimal
    current_spending: Decimal
    percentage_used: float
    alert_level: Literal["warning", "critical", "exceeded"]


# =============================================================================
# AGENT-SPECIFIC SCHEMAS (for n8n integration)
# =============================================================================

class AgentLogExpenseRequest(BaseSchema):
    """Request from n8n agent to log an expense."""
    
    amount: Decimal = Field(..., gt=0, description="Expense amount")
    category: str = Field(..., description="Category name (will be matched or created)")
    description: str | None = Field(None, description="Optional description")
    expense_date: date | None = Field(None, description="Expense date (defaults to today)")


class BudgetStatusInfo(BaseSchema):
    """Budget status info returned with expense registration."""
    
    category: str
    monthly_limit: Decimal
    spent_this_month: Decimal
    remaining: Decimal
    percentage_used: float


class AgentLogExpenseResponse(BaseSchema):
    """Response to agent after logging expense."""
    
    success: bool
    expense_id: UUID
    message: str
    alert: BudgetAlert | None = None
    budget_status: BudgetStatusInfo | None = None  # Always included if category has limit


class AgentGetReportRequest(BaseSchema):
    """Request from n8n agent for a report."""
    
    period: Literal["day", "week", "month", "year"] = "month"
    category: str | None = None


class AgentGetReportResponse(BaseSchema):
    """Simplified report response for agent."""
    
    period: str
    total_spent: Decimal
    transaction_count: int
    by_category: list[CategorySummary]
    top_category: str | None
    daily_average: Decimal


class AgentGetBudgetRequest(BaseSchema):
    """Request from n8n agent for budget status."""
    
    category: str | None = None


class AgentBudgetStatus(BaseSchema):
    """Budget status for a single category."""
    
    category: str
    limit: Decimal | None
    spent: Decimal
    remaining: Decimal | None
    percentage: float
    status: Literal["ok", "warning", "critical", "exceeded"]


class AgentGetBudgetResponse(BaseSchema):
    """Budget status response for agent."""
    
    budgets: list[AgentBudgetStatus]
    alerts: list[str]


class AgentDeleteExpenseRequest(BaseSchema):
    """Request from n8n agent to delete an expense."""

    expense_id: UUID | None = Field(None, description="Exact expense ID to delete")
    amount: Decimal | None = Field(None, description="Amount to match")
    category: str | None = Field(None, description="Category to match")
    description: str | None = Field(None, description="Description to match (partial)")
    expense_date: date | None = Field(None, description="Date to match (defaults to today)")


class AgentDeleteExpenseResponse(BaseSchema):
    """Response after deleting expense."""
    
    success: bool
    message: str
    deleted_expense: dict | None = None


class AgentModifyExpenseRequest(BaseSchema):
    """Request from n8n agent to modify an expense."""

    expense_id: UUID | None = Field(None, description="Exact expense ID to modify")
    # Search criteria
    search_amount: Decimal | None = Field(None, description="Amount to search for")
    search_category: str | None = Field(None, description="Category to search for")
    search_description: str | None = Field(None, description="Description to search for")
    search_date: date | None = Field(None, description="Date to search for (defaults to today)")
    
    # New values
    new_amount: Decimal | None = Field(None, gt=0, description="New amount")
    new_category: str | None = Field(None, description="New category")
    new_description: str | None = Field(None, description="New description")


class AgentModifyExpenseResponse(BaseSchema):
    """Response after modifying expense."""
    
    success: bool
    message: str
    modified_expense: dict | None = None


class AgentSetBudgetRequest(BaseSchema):
    """Request from n8n agent to set a budget."""

    category_id: UUID | None = Field(None, description="Optional category ID for deterministic updates")
    category: str = Field(..., description="Category name")
    monthly_limit: Decimal = Field(..., ge=0, description="Monthly budget limit (0 = no limit)")
    alert_threshold: int = Field(default=80, ge=0, le=100, description="Alert threshold percentage")


class AgentSetBudgetResponse(BaseSchema):
    """Response after setting a budget."""
    
    success: bool
    message: str
    budget: dict | None = None
    created: bool = False  # True if category was created, False if updated


class AgentCategoryItem(BaseSchema):
    """Single category item for agent list."""

    id: UUID
    name: str
    monthly_limit: Decimal | None = None
    current_spending: Decimal = Decimal("0")
    parent_id: UUID | None = None
    is_system: bool = False


class AgentListCategoriesResponse(BaseSchema):
    """Response with list of categories for agent."""
    
    categories: list[AgentCategoryItem]
    count: int


class AgentLogIncomeResponse(BaseSchema):
    """Response to agent after logging income."""
    success: bool
    income_id: UUID
    message: str


class AgentCreateCategoryRequest(BaseSchema):
    """Request to create a category for agent flows."""

    name: str = Field(..., min_length=1, max_length=100)
    monthly_limit: Decimal | None = Field(None, ge=0)
    alert_threshold: int = Field(default=80, ge=0, le=100)
    parent_id: UUID | None = None


class AgentCreateCategoryResponse(BaseSchema):
    """Response after creating a category."""

    success: bool
    message: str
    category: AgentCategoryItem | None = None


class AgentUpdateCategoryRequest(BaseSchema):
    """Request to update a category by id or name."""

    category_id: UUID | None = None
    category_name: str | None = Field(None, min_length=1, max_length=100)
    new_name: str | None = Field(None, min_length=1, max_length=100)
    monthly_limit: Decimal | None = Field(None, ge=0)
    alert_threshold: int | None = Field(None, ge=0, le=100)


class AgentUpdateCategoryResponse(BaseSchema):
    """Response after updating a category."""

    success: bool
    message: str
    category: AgentCategoryItem | None = None


class AgentDeleteCategoryRequest(BaseSchema):
    """Request to delete a category by id or name."""

    category_id: UUID | None = None
    category_name: str | None = Field(None, min_length=1, max_length=100)


class AgentDeleteCategoryResponse(BaseSchema):
    """Response after deleting a category."""

    success: bool
    message: str
    deleted_category_id: UUID | None = None
    blocked_has_expenses: bool = False


class AgentDeleteBudgetRequest(BaseSchema):
    """Request to remove monthly limit from a category budget."""

    category_id: UUID | None = None
    category_name: str | None = Field(None, min_length=1, max_length=100)


class AgentDeleteBudgetResponse(BaseSchema):
    """Response after deleting a budget limit."""

    success: bool
    message: str
    category: AgentCategoryItem | None = None
