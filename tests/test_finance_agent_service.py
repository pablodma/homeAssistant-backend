"""Tests for finance service agent-specific deterministic flows."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from src.app.services import finance as finance_service


@pytest.mark.asyncio
async def test_delete_expense_for_agent_by_expense_id(monkeypatch):
    """Delete by expense_id should bypass fuzzy search criteria."""
    tenant_id = uuid4()
    expense_id = uuid4()

    expense_row = {
        "id": expense_id,
        "amount": Decimal("2500"),
        "category_name": "Supermercado",
        "description": "pan",
        "expense_date": date(2026, 2, 28),
    }

    async def fake_get_expense_by_id(arg_tenant_id, arg_expense_id):
        assert arg_tenant_id == tenant_id
        assert arg_expense_id == expense_id
        return expense_row

    async def fake_delete_expense(arg_tenant_id, arg_expense_id):
        assert arg_tenant_id == tenant_id
        assert arg_expense_id == expense_id
        return True

    monkeypatch.setattr(
        finance_service.repo,
        "get_expense_by_id",
        fake_get_expense_by_id,
    )
    monkeypatch.setattr(finance_service.repo, "delete_expense", fake_delete_expense)

    result = await finance_service.delete_expense_for_agent(
        tenant_id=tenant_id,
        expense_id=expense_id,
    )

    assert result["success"] is True
    assert "Gasto eliminado" in result["message"]
    assert result["deleted_expense"]["id"] == str(expense_id)


@pytest.mark.asyncio
async def test_modify_expense_for_agent_by_expense_id(monkeypatch):
    """Modify by expense_id should be deterministic and update amount."""
    tenant_id = uuid4()
    expense_id = uuid4()

    existing_row = {
        "id": expense_id,
        "amount": Decimal("5000"),
        "description": "nafta",
        "expense_date": date(2026, 2, 20),
        "category_name": "Transporte",
    }
    updated_row = {
        "id": expense_id,
        "amount": Decimal("6500"),
        "description": "nafta",
        "expense_date": date(2026, 2, 20),
    }

    async def fake_get_expense_by_id(arg_tenant_id, arg_expense_id):
        assert arg_tenant_id == tenant_id
        assert arg_expense_id == expense_id
        return existing_row

    async def fake_update_expense(arg_tenant_id, arg_expense_id, **updates):
        assert arg_tenant_id == tenant_id
        assert arg_expense_id == expense_id
        assert updates["amount"] == Decimal("6500")
        return updated_row

    monkeypatch.setattr(
        finance_service.repo,
        "get_expense_by_id",
        fake_get_expense_by_id,
    )
    monkeypatch.setattr(finance_service.repo, "update_expense", fake_update_expense)

    result = await finance_service.modify_expense_for_agent(
        tenant_id=tenant_id,
        expense_id=expense_id,
        new_amount=Decimal("6500"),
    )

    assert result["success"] is True
    assert "Gasto modificado" in result["message"]
    assert result["modified_expense"]["id"] == str(expense_id)


@pytest.mark.asyncio
async def test_delete_category_for_agent_blocks_when_has_expenses(monkeypatch):
    """Deleting category with linked expenses should be blocked."""
    tenant_id = uuid4()
    category_id = uuid4()

    async def fake_get_budget_category_by_id(arg_tenant_id, arg_category_id):
        assert arg_tenant_id == tenant_id
        assert arg_category_id == category_id
        return {"id": category_id, "name": "Mascotas"}

    async def fake_count_expenses_by_category(arg_tenant_id, arg_category_id):
        assert arg_tenant_id == tenant_id
        assert arg_category_id == category_id
        return 3

    monkeypatch.setattr(
        finance_service.repo,
        "get_budget_category_by_id",
        fake_get_budget_category_by_id,
    )
    monkeypatch.setattr(
        finance_service.repo,
        "count_expenses_by_category",
        fake_count_expenses_by_category,
    )

    result = await finance_service.delete_category_for_agent(
        tenant_id=tenant_id,
        category_id=category_id,
    )

    assert result["success"] is False
    assert result["blocked_has_expenses"] is True
    assert "tiene gastos asociados" in result["message"]
