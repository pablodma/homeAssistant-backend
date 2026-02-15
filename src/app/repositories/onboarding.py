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

    async def create_member(
        self,
        tenant_id: UUID,
        phone: str,
        display_name: str,
        role: str = "member",
        email: str | None = None,
    ) -> UUID:
        """
        Create a new user (member) in a tenant.
        
        Used during onboarding to create user records for household members.
        """
        pool = await get_pool()
        
        normalized_phone = self._normalize_phone(phone)
        
        query = """
            INSERT INTO users (
                tenant_id, phone, email, display_name, role,
                phone_verified, is_active, auth_provider, created_at
            )
            VALUES ($1, $2, $3, $4, $5, false, true, 'whatsapp', NOW())
            ON CONFLICT (phone) WHERE phone IS NOT NULL DO UPDATE SET
                tenant_id = EXCLUDED.tenant_id,
                display_name = EXCLUDED.display_name,
                role = EXCLUDED.role,
                email = COALESCE(EXCLUDED.email, users.email)
            RETURNING id
        """
        
        user_id = await pool.fetchval(
            query,
            tenant_id,
            normalized_phone,
            email,
            display_name,
            role,
        )
        
        return UUID(str(user_id))

    async def update_user_phone(
        self,
        user_id: UUID,
        phone: str,
    ) -> None:
        """Update an existing user's phone number (e.g., owner adding their WhatsApp)."""
        pool = await get_pool()
        
        normalized_phone = self._normalize_phone(phone)
        
        await pool.execute(
            "UPDATE users SET phone = $1 WHERE id = $2",
            normalized_phone,
            user_id,
        )

    def _normalize_phone(self, phone: str) -> str:
        """
        Normalize phone number to E.164 format.
        
        WhatsApp webhooks may send numbers without the '+' prefix,
        but we store them with '+'. This ensures consistent lookups.
        """
        phone = phone.strip()
        if not phone.startswith("+"):
            phone = f"+{phone}"
        return phone

    async def get_tenant_by_phone(self, phone: str) -> dict[str, Any] | None:
        """
        Get tenant info by phone number.
        
        Used by the bot for multitenancy resolution.
        Looks up directly in the users table (source of truth).
        Normalizes the phone number to E.164 format before lookup.
        """
        pool = await get_pool()
        
        # Normalize phone to E.164 format (with '+' prefix)
        normalized_phone = self._normalize_phone(phone)
        
        query = """
            SELECT 
                u.tenant_id,
                u.id as user_id,
                u.display_name as user_name,
                (u.role IN ('owner', 'admin')) as is_primary,
                t.home_name,
                t.plan,
                t.timezone,
                t.language,
                t.currency
            FROM users u
            JOIN tenants t ON u.tenant_id = t.id
            WHERE u.phone = $1
              AND u.is_active = true
        """
        
        row = await pool.fetchrow(query, normalized_phone)
        return dict(row) if row else None

    async def get_members_by_tenant(self, tenant_id: UUID) -> list[dict[str, Any]]:
        """Get all members (users) for a tenant."""
        pool = await get_pool()
        
        query = """
            SELECT 
                id, phone, email, display_name, role, 
                phone_verified, email_verified, avatar_url,
                is_active, created_at
            FROM users
            WHERE tenant_id = $1
              AND is_active = true
            ORDER BY 
                CASE role WHEN 'owner' THEN 0 WHEN 'admin' THEN 1 ELSE 2 END,
                created_at ASC
        """
        
        rows = await pool.fetch(query, tenant_id)
        return [dict(row) for row in rows]

    async def remove_member(self, user_id: UUID, tenant_id: UUID) -> bool:
        """Soft-delete a member from a tenant. Returns True if updated."""
        pool = await get_pool()
        
        result = await pool.execute(
            "UPDATE users SET is_active = false WHERE id = $1 AND tenant_id = $2",
            user_id,
            tenant_id,
        )
        
        return result == "UPDATE 1"

    async def check_phone_exists(self, phone: str) -> bool:
        """Check if a phone is already registered to any user."""
        pool = await get_pool()
        
        normalized_phone = self._normalize_phone(phone)
        
        exists = await pool.fetchval(
            "SELECT EXISTS(SELECT 1 FROM users WHERE phone = $1 AND is_active = true)",
            normalized_phone,
        )
        
        return bool(exists)

    async def create_default_budget_categories(self, tenant_id: UUID) -> None:
        """Create default budget categories for a new tenant."""
        pool = await get_pool()
        
        # Categorías base con presupuesto $0 (sin límite inicial)
        # El usuario puede configurar límites después
        categories = [
            ("Supermercado", 0, 80),
            ("Transporte", 0, 80),
            ("Servicios", 0, 80),
            ("Entretenimiento", 0, 80),
            ("Salud", 0, 80),
            ("Educación", 0, 80),
            ("Otros", 0, 80),
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
