"""Tests for access policy decision matrix."""

from uuid import uuid4

import pytest

from src.app.services.access_policy import AccessPolicyService


@pytest.mark.parametrize(
    "tenant_id,onboarding_completed,tenant_active,subscription_status,expected_next_step,expected_access",
    [
        (None, False, False, None, "register", False),
        (uuid4(), False, True, None, "onboarding", False),
        (uuid4(), True, True, "pending", "subscribe", False),
        (uuid4(), True, True, "cancelled", "subscribe", False),
        (uuid4(), True, False, "authorized", "contact_support", False),
        (uuid4(), True, True, "authorized", "dashboard", True),
    ],
)
def test_build_access_status_matrix(
    tenant_id,
    onboarding_completed,
    tenant_active,
    subscription_status,
    expected_next_step,
    expected_access,
):
    result = AccessPolicyService._build_access_status(
        tenant_id=tenant_id,
        user_name="Pablo" if tenant_id else None,
        home_name="Casa" if tenant_id else None,
        onboarding_completed=onboarding_completed,
        tenant_active=tenant_active,
        subscription_status=subscription_status,
    )

    assert result.next_step == expected_next_step
    assert result.can_access_dashboard is expected_access
    assert result.can_interact_agent is expected_access
    assert result.has_active_subscription is (subscription_status == "authorized")
