"""Repository for onboarding operations."""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from ..config.database import get_pool


class OnboardingRepository:
    """Repository for onboarding-related database operations."""

    async def get_user_tenant(self, user_id: UUID) -> dict[str, Any] | None:
        """
        Get the tenant for a user by their ID.
        
        Returns tenant info if user has completed onboarding.
        """
        pool = await get_pool()
        
        query = """
            SELECT 
                t.id as tenant_id,
                t.home_name,
                t.plan,
                t.onboarding_completed,
                t.timezone,
                t.language,
                t.currency
            FROM users u
            JOIN tenants t ON u.tenant_id = t.id
            WHERE u.id = $1
        """
        
        row = await pool.fetchrow(query, user_id)
        return dict(row) if row else None

    async def create_tenant(
        self,
        home_name: str,
        plan: str,
        owner_user_id: UUID,
        timezone: str = "America/Argentina/Buenos_Aires",
        language: str = "es-AR",
        currency: str = "ARS",
    ) -> UUID:
        """
        Create a new tenant.
        
        Returns the new tenant ID.
        """
        pool = await get_pool()
        
        query = """
            INSERT INTO tenants (
                name, home_name, plan, owner_user_id, 
                onboarding_completed, timezone, language, currency, settings
            )
            VALUES ($1, $2, $3, $4, true, $5, $6, $7, '{}'::jsonb)
            RETURNING id
        """
        
        tenant_id = await pool.fetchval(
            query,
            home_name,  # name = home_name for simplicity
            home_name,
            plan,
            owner_user_id,
            timezone,
            language,
            currency,
        )
        
        return UUID(str(tenant_id))

    async def update_user_tenant(self, user_id: UUID, tenant_id: UUID) -> None:
        """Update user's tenant_id after onboarding."""
        pool = await get_pool()
        
        await pool.execute(
            "UPDATE users SET tenant_id = $1 WHERE id = $2",
            tenant_id,
            user_id,
        )

    async def register_phone(
        self,
        phone: str,
        tenant_id: UUID,
        user_id: UUID | None,
        display_name: str,
        is_primary: bool = False,
    ) -> UUID:
        """
        Register a phone number to a tenant.
        
        Creates the mapping and optionally links to a user.
        """
        pool = await get_pool()
        
        query = """
            INSERT INTO phone_tenant_mapping (
                phone, tenant_id, user_id, display_name, is_primary, verified_at
            )
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (phone) DO UPDATE SET
                tenant_id = EXCLUDED.tenant_id,
                user_id = EXCLUDED.user_id,
                display_name = EXCLUDED.display_name,
                is_primary = EXCLUDED.is_primary,
                verified_at = EXCLUDED.verified_at,
                updated_at = NOW()
            RETURNING id
        """
        
        mapping_id = await pool.fetchval(
            query,
            phone,
            tenant_id,
            user_id,
            display_name,
            is_primary,
            datetime.now(timezone.utc),
        )
        
        return UUID(str(mapping_id))

    async def get_tenant_by_phone(self, phone: str) -> dict[str, Any] | None:
        """
        Get tenant info by phone number.
        
        Used by the bot for multitenancy resolution.
        """
        pool = await get_pool()
        
        query = """
            SELECT 
                ptm.tenant_id,
                ptm.user_id,
                ptm.display_name as user_name,
                ptm.is_primary,
                t.home_name,
                t.plan,
                t.timezone,
                t.language,
                t.currency
            FROM phone_tenant_mapping ptm
            JOIN tenants t ON ptm.tenant_id = t.id
            WHERE ptm.phone = $1
        """
        
        row = await pool.fetchrow(query, phone)
        return dict(row) if row else None

    async def get_phones_by_tenant(self, tenant_id: UUID) -> list[dict[str, Any]]:
        """Get all phone mappings for a tenant."""
        pool = await get_pool()
        
        query = """
            SELECT 
                id, phone, user_id, display_name, is_primary, verified_at, created_at
            FROM phone_tenant_mapping
            WHERE tenant_id = $1
            ORDER BY is_primary DESC, created_at ASC
        """
        
        rows = await pool.fetch(query, tenant_id)
        return [dict(row) for row in rows]

    async def delete_phone_mapping(self, phone: str, tenant_id: UUID) -> bool:
        """Remove a phone from a tenant. Returns True if deleted."""
        pool = await get_pool()
        
        result = await pool.execute(
            "DELETE FROM phone_tenant_mapping WHERE phone = $1 AND tenant_id = $2",
            phone,
            tenant_id,
        )
        
        return result == "DELETE 1"

    async def check_phone_exists(self, phone: str) -> bool:
        """Check if a phone is already registered."""
        pool = await get_pool()
        
        exists = await pool.fetchval(
            "SELECT EXISTS(SELECT 1 FROM phone_tenant_mapping WHERE phone = $1)",
            phone,
        )
        
        return bool(exists)

    async def create_default_budget_categories(self, tenant_id: UUID) -> None:
        """Create default budget categories for a new tenant."""
        pool = await get_pool()
        
        categories = [
            ("Supermercado", 50000, 80),
            ("Transporte", 20000, 80),
            ("Entretenimiento", 15000, 80),
            ("Servicios", 30000, 90),
            ("Salud", 10000, 80),
            ("Educación", 15000, 80),
            ("Otros", 10000, 80),
        ]
        
        query = """
            INSERT INTO budget_categories (tenant_id, name, monthly_limit, alert_threshold_percent)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT DO NOTHING
        """
        
        for name, limit, threshold in categories:
            await pool.execute(query, tenant_id, name, limit, threshold)


# Singleton instance
_repository: OnboardingRepository | None = None


def get_onboarding_repository() -> OnboardingRepository:
    """Get or create the onboarding repository instance."""
    global _repository
    if _repository is None:
        _repository = OnboardingRepository()
    return _repository
