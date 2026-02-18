"""Repository for agent first-time-use onboarding tracking."""

from datetime import datetime, timezone
from typing import Any

from ..config.database import get_pool


class AgentOnboardingRepository:
    """Repository for tracking per-user, per-agent first-time onboarding."""

    def _normalize_phone(self, phone: str) -> str:
        """Normalize phone number to E.164 format."""
        phone = phone.strip()
        if not phone.startswith("+"):
            phone = f"+{phone}"

        if phone.startswith("+54") and not phone.startswith("+549"):
            rest = phone[3:]
            if len(rest) == 10:
                phone = f"+549{rest}"

        return phone

    def _phone_variants(self, phone: str) -> list[str]:
        """Build phone variants for Argentina compatibility."""
        normalized = self._normalize_phone(phone)
        variants = [normalized]
        if normalized.startswith("+549"):
            variants.append(f"+54{normalized[4:]}")
        return variants

    async def get_status(self, phone: str, agent_name: str) -> bool:
        """Check if a user has completed first-time onboarding for an agent.

        Args:
            phone: User phone number.
            agent_name: Agent identifier (finance, calendar, etc.).

        Returns:
            True if first time (not completed), False if already onboarded.
        """
        pool = await get_pool()
        phone_variants = self._phone_variants(phone)

        row = await pool.fetchrow(
            """
            SELECT uao.completed
            FROM user_agent_onboarding uao
            JOIN users u ON u.id = uao.user_id
            WHERE u.phone = ANY($1)
              AND u.is_active = true
              AND uao.agent_name = $2
            """,
            phone_variants,
            agent_name,
        )

        if row is None:
            return True  # No record = first time

        return not row["completed"]

    async def complete(self, phone: str, agent_name: str) -> bool:
        """Mark agent onboarding as completed for a user.

        Args:
            phone: User phone number.
            agent_name: Agent identifier.

        Returns:
            True if successfully marked, False if user not found.
        """
        pool = await get_pool()
        phone_variants = self._phone_variants(phone)

        # Resolve user_id from phone
        user_row = await pool.fetchrow(
            """
            SELECT id FROM users
            WHERE phone = ANY($1) AND is_active = true
            """,
            phone_variants,
        )

        if not user_row:
            return False

        user_id = user_row["id"]

        await pool.execute(
            """
            INSERT INTO user_agent_onboarding (user_id, agent_name, completed, completed_at)
            VALUES ($1, $2, true, $3)
            ON CONFLICT (user_id, agent_name)
            DO UPDATE SET completed = true, completed_at = $3
            """,
            user_id,
            agent_name,
            datetime.now(timezone.utc),
        )

        return True


# Singleton instance
_repository: AgentOnboardingRepository | None = None


def get_agent_onboarding_repository() -> AgentOnboardingRepository:
    """Get or create the agent onboarding repository instance."""
    global _repository
    if _repository is None:
        _repository = AgentOnboardingRepository()
    return _repository
