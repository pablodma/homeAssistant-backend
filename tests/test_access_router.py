"""Tests for access policy endpoints."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.app.main import app
from src.app.middleware.auth import get_current_user, require_service_token
from src.app.routers import access as access_router
from src.app.schemas.access import AccessStatusResponse
from src.app.schemas.auth import CurrentUser


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


def _mock_user() -> CurrentUser:
    return CurrentUser(
        id=uuid4(),
        tenant_id=uuid4(),
        email="test@homeai.local",
        role="owner",
        onboarding_completed=True,
    )


def test_get_access_status_for_web_user(client, monkeypatch):
    """Web endpoint should return unified access status."""

    class _FakeService:
        async def get_access_status_for_user(self, user_id):  # noqa: ARG002
            return AccessStatusResponse(
                tenant_id=uuid4(),
                user_name="Pablo",
                home_name="Mi hogar",
                is_registered=True,
                onboarding_completed=True,
                tenant_active=True,
                subscription_status="authorized",
                has_active_subscription=True,
                can_access_dashboard=True,
                can_interact_agent=True,
                next_step="dashboard",
            )

    app.dependency_overrides[get_current_user] = _mock_user
    monkeypatch.setattr(
        access_router,
        "get_access_policy_service",
        lambda: _FakeService(),
    )

    try:
        response = client.get("/api/v1/access/status")
        assert response.status_code == 200
        data = response.json()
        assert data["is_registered"] is True
        assert data["has_active_subscription"] is True
        assert data["next_step"] == "dashboard"
    finally:
        app.dependency_overrides.clear()


def test_get_access_status_by_phone_for_bot(client, monkeypatch):
    """Bot endpoint should expose subscribe step when not authorized."""

    class _FakeService:
        async def get_access_status_by_phone(self, phone):  # noqa: ARG002
            return AccessStatusResponse(
                tenant_id=uuid4(),
                user_name="Pablo",
                home_name="Mi hogar",
                is_registered=True,
                onboarding_completed=True,
                tenant_active=True,
                subscription_status="pending",
                has_active_subscription=False,
                can_access_dashboard=False,
                can_interact_agent=False,
                next_step="subscribe",
            )

    app.dependency_overrides[require_service_token] = _mock_user
    monkeypatch.setattr(
        access_router,
        "get_access_policy_service",
        lambda: _FakeService(),
    )

    try:
        response = client.get("/api/v1/access/status-by-phone", params={"phone": "+5491111111111"})
        assert response.status_code == 200
        data = response.json()
        assert data["subscription_status"] == "pending"
        assert data["can_interact_agent"] is False
        assert data["next_step"] == "subscribe"
    finally:
        app.dependency_overrides.clear()
