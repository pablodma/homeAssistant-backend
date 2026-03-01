"""Access policy service to centralize onboarding/subscription checks."""

from uuid import UUID

from ..config.database import get_pool
from ..repositories import subscription_repo
from ..schemas.access import AccessStatusResponse


class AccessPolicyService:
    """Resolve whether a user/phone can access dashboard or agent."""

    @staticmethod
    def _normalize_phone(phone: str) -> str:
        """Normalize phone number to E.164 format with AR compatibility."""
        normalized = phone.strip()
        if not normalized.startswith("+"):
            normalized = f"+{normalized}"

        # Argentina mobile normalization: +54XX... -> +549XX...
        if normalized.startswith("+54") and not normalized.startswith("+549"):
            rest = normalized[3:]
            if len(rest) == 10:
                normalized = f"+549{rest}"

        return normalized

    @staticmethod
    def _phone_variants(phone: str) -> list[str]:
        """Build phone variants to support legacy Argentina records."""
        normalized = AccessPolicyService._normalize_phone(phone)
        variants = [normalized]
        if normalized.startswith("+549"):
            variants.append(f"+54{normalized[4:]}")
        return variants

    @staticmethod
    def _build_access_status(
        *,
        tenant_id: UUID | None,
        user_name: str | None,
        home_name: str | None,
        onboarding_completed: bool,
        tenant_active: bool,
        subscription_status: str | None,
    ) -> AccessStatusResponse:
        """Build deterministic access flags and next step."""
        has_tenant = tenant_id is not None
        is_registered = has_tenant and onboarding_completed
        has_active_subscription = subscription_status == "authorized"

        can_access = (
            has_tenant
            and is_registered
            and tenant_active
            and has_active_subscription
        )

        if not has_tenant:
            next_step = "register"
        elif not onboarding_completed:
            next_step = "onboarding"
        elif not tenant_active:
            next_step = "contact_support"
        elif not has_active_subscription:
            next_step = "subscribe"
        else:
            next_step = "dashboard"

        return AccessStatusResponse(
            tenant_id=tenant_id,
            user_name=user_name,
            home_name=home_name,
            is_registered=is_registered,
            onboarding_completed=onboarding_completed,
            tenant_active=tenant_active,
            subscription_status=subscription_status,
            has_active_subscription=has_active_subscription,
            can_access_dashboard=can_access,
            can_interact_agent=can_access,
            next_step=next_step,
        )

    async def get_access_status_for_user(self, user_id: UUID) -> AccessStatusResponse:
        """Get access status for authenticated web user."""
        pool = await get_pool()
        row = await pool.fetchrow(
            """
            SELECT
                u.display_name AS user_name,
                t.id AS tenant_id,
                t.home_name,
                COALESCE(t.onboarding_completed, false) AS onboarding_completed,
                COALESCE(t.active, true) AS tenant_active
            FROM users u
            LEFT JOIN tenants t ON u.tenant_id = t.id
            WHERE u.id = $1
              AND u.is_active = true
            LIMIT 1
            """,
            user_id,
        )

        if not row or not row["tenant_id"]:
            return self._build_access_status(
                tenant_id=None,
                user_name=None,
                home_name=None,
                onboarding_completed=False,
                tenant_active=False,
                subscription_status=None,
            )

        tenant_id = UUID(str(row["tenant_id"]))
        subscription = await subscription_repo.get_subscription_by_tenant(tenant_id)
        subscription_status = (
            str(subscription["status"]) if subscription and subscription.get("status") else None
        )

        return self._build_access_status(
            tenant_id=tenant_id,
            user_name=row.get("user_name"),
            home_name=row.get("home_name"),
            onboarding_completed=bool(row.get("onboarding_completed")),
            tenant_active=bool(row.get("tenant_active")),
            subscription_status=subscription_status,
        )

    async def get_access_status_by_phone(self, phone: str) -> AccessStatusResponse:
        """Get access status for bot flow by phone lookup."""
        phone_variants = self._phone_variants(phone)
        pool = await get_pool()
        row = await pool.fetchrow(
            """
            SELECT
                u.display_name AS user_name,
                t.id AS tenant_id,
                t.home_name,
                COALESCE(t.onboarding_completed, false) AS onboarding_completed,
                COALESCE(t.active, true) AS tenant_active
            FROM users u
            JOIN tenants t ON u.tenant_id = t.id
            WHERE u.phone = ANY($1)
              AND u.is_active = true
            LIMIT 1
            """,
            phone_variants,
        )

        if not row or not row["tenant_id"]:
            return self._build_access_status(
                tenant_id=None,
                user_name=None,
                home_name=None,
                onboarding_completed=False,
                tenant_active=False,
                subscription_status=None,
            )

        tenant_id = UUID(str(row["tenant_id"]))
        subscription = await subscription_repo.get_subscription_by_tenant(tenant_id)
        subscription_status = (
            str(subscription["status"]) if subscription and subscription.get("status") else None
        )

        return self._build_access_status(
            tenant_id=tenant_id,
            user_name=row.get("user_name"),
            home_name=row.get("home_name"),
            onboarding_completed=bool(row.get("onboarding_completed")),
            tenant_active=bool(row.get("tenant_active")),
            subscription_status=subscription_status,
        )


_access_policy_service: AccessPolicyService | None = None


def get_access_policy_service() -> AccessPolicyService:
    """Get singleton AccessPolicyService instance."""
    global _access_policy_service
    if _access_policy_service is None:
        _access_policy_service = AccessPolicyService()
    return _access_policy_service
