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


class AgentLogExpenseResponse(BaseSchema):
    """Response to agent after logging expense."""
    
    success: bool
    expense_id: UUID
    message: str
    alert: BudgetAlert | None = None


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
    
    category: str = Field(..., description="Category name")
    monthly_limit: Decimal = Field(..., gt=0, description="Monthly budget limit")
    alert_threshold: int = Field(default=80, ge=0, le=100, description="Alert threshold percentage")


class AgentSetBudgetResponse(BaseSchema):
    """Response after setting a budget."""
    
    success: bool
    message: str
    budget: dict | None = None
    created: bool = False  # True if category was created, False if updated
