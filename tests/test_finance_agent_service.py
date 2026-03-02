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


@pytest.mark.asyncio
async def test_create_expense_with_alert_first_expense_prompts_budget_for_category(monkeypatch):
    """First expense in a category should prompt to define category budget."""
    tenant_id = uuid4()
    category_id = uuid4()
    group_id = uuid4()
    expense_id = uuid4()

    async def fake_resolve_category(arg_tenant_id, arg_category_name):
        assert arg_tenant_id == tenant_id
        assert arg_category_name == "Combustible"
        return category_id

    async def fake_count_expenses_by_category(arg_tenant_id, arg_category_id):
        assert arg_tenant_id == tenant_id
        assert arg_category_id == category_id
        return 0

    async def fake_get_budget_category_by_id(arg_tenant_id, arg_category_id):
        assert arg_tenant_id == tenant_id
        if arg_category_id == category_id:
            return {
                "id": category_id,
                "name": "Combustible",
                "parent_id": group_id,
                "monthly_limit": None,
            }
        if arg_category_id == group_id:
            return {"id": group_id, "name": "Movilidad", "parent_id": None}
        return None

    async def fake_create_expense(**kwargs):
        assert kwargs["tenant_id"] == tenant_id
        assert kwargs["category_id"] == category_id
        assert kwargs["amount"] == Decimal("85000")
        return {"id": expense_id}

    async def fake_check_alert(*args, **kwargs):  # noqa: ARG001
        return None

    async def fake_budget_status(*args, **kwargs):  # noqa: ARG001
        return None

    monkeypatch.setattr(finance_service, "resolve_category", fake_resolve_category)
    monkeypatch.setattr(
        finance_service.repo,
        "count_expenses_by_category",
        fake_count_expenses_by_category,
    )
    monkeypatch.setattr(
        finance_service.repo,
        "get_budget_category_by_id",
        fake_get_budget_category_by_id,
    )
    monkeypatch.setattr(finance_service.repo, "create_expense", fake_create_expense)
    monkeypatch.setattr(finance_service, "check_category_alert", fake_check_alert)
    monkeypatch.setattr(finance_service, "get_budget_status_for_category", fake_budget_status)

    result = await finance_service.create_expense_with_alert(
        tenant_id=tenant_id,
        amount=Decimal("85000"),
        category_name="Combustible",
        description="combustible",
    )

    assert result.success is True
    assert str(result.expense_id) == str(expense_id)
    assert "Es tu primer gasto en Combustible" in result.message
    assert "definir un presupuesto mensual para Combustible" in result.message


@pytest.mark.asyncio
async def test_create_expense_with_alert_non_first_expense_does_not_prompt_budget(monkeypatch):
    """Non-first expense should keep regular follow-up prompt."""
    tenant_id = uuid4()
    category_id = uuid4()
    group_id = uuid4()
    expense_id = uuid4()

    async def fake_resolve_category(arg_tenant_id, arg_category_name):
        assert arg_tenant_id == tenant_id
        assert arg_category_name == "Combustible"
        return category_id

    async def fake_count_expenses_by_category(arg_tenant_id, arg_category_id):
        assert arg_tenant_id == tenant_id
        assert arg_category_id == category_id
        return 2

    async def fake_get_budget_category_by_id(arg_tenant_id, arg_category_id):
        assert arg_tenant_id == tenant_id
        if arg_category_id == category_id:
            return {
                "id": category_id,
                "name": "Combustible",
                "parent_id": group_id,
                "monthly_limit": None,
            }
        if arg_category_id == group_id:
            return {"id": group_id, "name": "Movilidad", "parent_id": None}
        return None

    async def fake_create_expense(**kwargs):
        assert kwargs["tenant_id"] == tenant_id
        assert kwargs["category_id"] == category_id
        assert kwargs["amount"] == Decimal("12000")
        return {"id": expense_id}

    async def fake_check_alert(*args, **kwargs):  # noqa: ARG001
        return None

    async def fake_budget_status(*args, **kwargs):  # noqa: ARG001
        return None

    monkeypatch.setattr(finance_service, "resolve_category", fake_resolve_category)
    monkeypatch.setattr(
        finance_service.repo,
        "count_expenses_by_category",
        fake_count_expenses_by_category,
    )
    monkeypatch.setattr(
        finance_service.repo,
        "get_budget_category_by_id",
        fake_get_budget_category_by_id,
    )
    monkeypatch.setattr(finance_service.repo, "create_expense", fake_create_expense)
    monkeypatch.setattr(finance_service, "check_category_alert", fake_check_alert)
    monkeypatch.setattr(finance_service, "get_budget_status_for_category", fake_budget_status)

    result = await finance_service.create_expense_with_alert(
        tenant_id=tenant_id,
        amount=Decimal("12000"),
        category_name="Combustible",
        description="nafta",
    )

    assert result.success is True
    assert str(result.expense_id) == str(expense_id)
    assert "Es tu primer gasto en Combustible" not in result.message
    assert "¿Querés ver el resumen del mes o cargar otro gasto?" in result.message
