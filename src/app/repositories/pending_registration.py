"""Repository for pending registration operations (WhatsApp onboarding)."""

from typing import Any
from uuid import UUID

from ..config.database import get_pool


class PendingRegistrationRepository:
    """Repository for pending_registrations table operations."""

    async def create(
        self,
        phone: str,
        display_name: str,
        home_name: str,
        plan_type: str,
        coupon_code: str | None = None,
        ls_checkout_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a new pending registration.

        Args:
            phone: User's phone number.
            display_name: User's display name.
            home_name: Name for the household.
            plan_type: Plan type (family, premium).
            coupon_code: Optional coupon code.
            ls_checkout_id: Optional Lemon Squeezy checkout ID.

        Returns:
            The created pending registration record.
        """
        pool = await get_pool()

        query = """
            INSERT INTO pending_registrations (
                phone, display_name, home_name, plan_type, 
                coupon_code, ls_checkout_id
            )
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING *
        """

        row = await pool.fetchrow(
            query,
            phone,
            display_name,
            home_name,
            plan_type,
            coupon_code,
            ls_checkout_id,
        )
        return dict(row)

    async def get_by_phone(self, phone: str) -> dict[str, Any] | None:
        """Get the latest pending registration for a phone.

        Args:
            phone: Phone number to look up.

        Returns:
            The pending registration or None.
        """
        pool = await get_pool()

        query = """
            SELECT * FROM pending_registrations
            WHERE phone = $1 
              AND status = 'pending'
              AND expires_at > NOW()
            ORDER BY created_at DESC
            LIMIT 1
        """

        row = await pool.fetchrow(query, phone)
        return dict(row) if row else None

    async def get_by_checkout_id(self, ls_checkout_id: str) -> dict[str, Any] | None:
        """Get pending registration by Lemon Squeezy checkout ID.

        Args:
            ls_checkout_id: The LS checkout ID.

        Returns:
            The pending registration or None.
        """
        pool = await get_pool()

        query = """
            SELECT * FROM pending_registrations
            WHERE ls_checkout_id = $1
              AND status = 'pending'
            LIMIT 1
        """

        row = await pool.fetchrow(query, ls_checkout_id)
        return dict(row) if row else None

    async def mark_completed(self, registration_id: UUID) -> None:
        """Mark a pending registration as completed.

        Args:
            registration_id: The registration ID to mark.
        """
        pool = await get_pool()

        await pool.execute(
            """
            UPDATE pending_registrations 
            SET status = 'completed', updated_at = NOW()
            WHERE id = $1
            """,
            registration_id,
        )

    async def update_checkout_id(
        self, registration_id: UUID, ls_checkout_id: str
    ) -> None:
        """Update the LS checkout ID on a pending registration.

        Args:
            registration_id: The registration ID.
            ls_checkout_id: The Lemon Squeezy checkout ID.
        """
        pool = await get_pool()

        await pool.execute(
            """
            UPDATE pending_registrations 
            SET ls_checkout_id = $1, updated_at = NOW()
            WHERE id = $2
            """,
            ls_checkout_id,
            registration_id,
        )

    async def cleanup_expired(self) -> int:
        """Mark expired pending registrations.

        Returns:
            Number of registrations marked as expired.
        """
        pool = await get_pool()

        result = await pool.execute(
            """
            UPDATE pending_registrations
            SET status = 'expired', updated_at = NOW()
            WHERE status = 'pending' AND expires_at < NOW()
            """
        )
        count = int(result.split()[-1]) if result else 0
        return count


# Singleton instance
_repository: PendingRegistrationRepository | None = None


def get_pending_registration_repository() -> PendingRegistrationRepository:
    """Get or create the pending registration repository instance."""
    global _repository
    if _repository is None:
        _repository = PendingRegistrationRepository()
    return _repository
