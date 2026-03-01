"""Access policy schemas."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from .subscription import SubscriptionStatus

AccessNextStep = Literal[
    "register",
    "onboarding",
    "subscribe",
    "dashboard",
    "contact_support",
]


class AccessStatusResponse(BaseModel):
    """Unified access status used by web and bot."""

    tenant_id: UUID | None = None
    user_name: str | None = None
    home_name: str | None = None

    is_registered: bool
    onboarding_completed: bool
    tenant_active: bool

    subscription_status: SubscriptionStatus | None = None
    has_active_subscription: bool

    can_access_dashboard: bool
    can_interact_agent: bool
    next_step: AccessNextStep
