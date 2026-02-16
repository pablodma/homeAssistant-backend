"""Subscription service for business logic and Lemon Squeezy integration."""

import logging
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from ..config.lemonsqueezy import PLAN_VARIANT_MAP, get_ls_client
from ..repositories import coupon_repo, plan_pricing_repo, subscription_repo
from ..schemas.subscription import (
    SubscriptionCreateResponse,
    SubscriptionStatusResponse,
)

logger = logging.getLogger(__name__)


class SubscriptionService:
    """Service for managing subscriptions with Lemon Squeezy."""

    def __init__(self) -> None:
        self.ls_client = get_ls_client()

    async def create_subscription(
        self,
        tenant_id: UUID,
        plan_type: str,
        payer_email: str,
        coupon_code: str | None = None,
        redirect_url: str | None = None,
    ) -> SubscriptionCreateResponse:
        """
        Create a new subscription for a tenant.

        Args:
            tenant_id: The tenant ID
            plan_type: Plan type (starter, family or premium)
            payer_email: Payer's email
            coupon_code: Optional coupon code for discount
            redirect_url: Optional redirect URL after LS checkout (from frontend origin)

        Returns:
            SubscriptionCreateResponse with checkout URL and pricing
        """
        # Validate plan type
        if plan_type not in ("starter", "family", "premium"):
            raise ValueError(f"Invalid plan type: {plan_type}")

        # Validate tenant exists in DB
        tenant = await subscription_repo.get_tenant_by_id(tenant_id)
        if not tenant:
            raise ValueError(
                "Tu cuenta no está configurada correctamente. "
                "Por favor, cerrá sesión e iniciá sesión nuevamente."
            )

        # Get variant ID for this plan
        variant_id = PLAN_VARIANT_MAP.get(plan_type)
        if not variant_id:
            raise ValueError(f"No Lemon Squeezy variant configured for plan: {plan_type}")

        # Get plan pricing from DB
        plan = await plan_pricing_repo.get_plan_by_type(plan_type)
        if not plan:
            raise ValueError(f"Plan not found: {plan_type}")

        original_price = Decimal(str(plan["price_monthly"]))
        discount_percent = None
        final_price = original_price
        coupon_id = None

        # Validate and apply coupon if provided
        if coupon_code:
            is_valid, coupon, error = await coupon_repo.validate_coupon(
                code=coupon_code,
                plan_type=plan_type,
                tenant_id=tenant_id,
            )

            if not is_valid:
                raise ValueError(error or "Invalid coupon")

            if coupon:
                coupon_id = coupon["id"]
                discount_percent = coupon["discount_percent"]
                discount_amount = original_price * Decimal(discount_percent) / 100
                final_price = original_price - discount_amount

        # Create subscription record in our DB
        subscription = await subscription_repo.create_subscription(
            tenant_id=tenant_id,
            plan_type=plan_type,
            status="pending",
        )

        checkout_url = None

        # Create Lemon Squeezy checkout if configured
        if self.ls_client.is_configured:
            # LS uses cents for custom prices
            custom_price_cents = int(final_price * 100) if coupon_code else None

            checkout = await self.ls_client.create_checkout(
                variant_id=variant_id,
                email=payer_email,
                custom_data={
                    "tenant_id": str(tenant_id),
                    "subscription_id": str(subscription["id"]),
                    "plan_type": plan_type,
                },
                redirect_url=redirect_url,
                custom_price=custom_price_cents,
                discount_code=coupon_code if not custom_price_cents else None,
            )

            if checkout:
                # Update subscription with LS checkout ID
                await subscription_repo.update_subscription(
                    subscription_id=subscription["id"],
                    ls_checkout_id=checkout["id"],
                )
                checkout_url = checkout["url"]
            else:
                # LS failed to create checkout – mark as cancelled and raise error
                logger.error(
                    f"LS failed to create checkout for subscription {subscription['id']}. "
                    f"Plan: {plan_type}, price: {final_price}, email: {payer_email}"
                )
                await subscription_repo.update_subscription_status(
                    subscription_id=subscription["id"],
                    status="cancelled",
                )
                raise RuntimeError(
                    f"No se pudo crear el checkout en Lemon Squeezy. "
                    f"Verifica que el plan ({plan_type}) esté correctamente configurado."
                )
        else:
            # LS not configured – cannot process paid plans
            logger.error("Lemon Squeezy is not configured – cannot process paid subscription")
            await subscription_repo.update_subscription_status(
                subscription_id=subscription["id"],
                status="cancelled",
            )
            raise RuntimeError("El sistema de pagos no está configurado. Contacta al soporte.")

        # Register coupon redemption if used
        if coupon_id and coupon_code:
            await coupon_repo.create_redemption(
                coupon_id=coupon_id,
                tenant_id=tenant_id,
                original_price=original_price,
                discount_applied=original_price - final_price,
                final_price=final_price,
                subscription_id=subscription["id"],
            )

        return SubscriptionCreateResponse(
            subscription_id=subscription["id"],
            checkout_url=checkout_url,
            original_price=original_price,
            discount_percent=discount_percent,
            final_price=final_price,
            plan_type=plan_type,
        )

    async def get_subscription_status(
        self,
        tenant_id: UUID,
        current_plan: str = "starter",
    ) -> SubscriptionStatusResponse:
        """Get current subscription status for a tenant."""
        subscription = await subscription_repo.get_subscription_by_tenant(tenant_id)

        has_subscription = subscription is not None and subscription["status"] == "authorized"

        return SubscriptionStatusResponse(
            has_subscription=has_subscription,
            subscription=subscription,
            current_plan=current_plan,
            can_upgrade=current_plan in ("starter", "family"),
            can_downgrade=current_plan in ("family", "premium"),
        )

    async def cancel_subscription(
        self,
        tenant_id: UUID,
        reason: str | None = None,
    ) -> tuple[bool, str]:
        """
        Cancel a subscription.

        Returns:
            Tuple of (success, message)
        """
        subscription = await subscription_repo.get_subscription_by_tenant(tenant_id)

        if not subscription:
            return False, "No active subscription found"

        if subscription["status"] not in ("authorized", "paused"):
            return False, f"Cannot cancel subscription in status: {subscription['status']}"

        # Cancel in Lemon Squeezy if we have a subscription ID
        if subscription.get("ls_subscription_id") and self.ls_client.is_configured:
            success = await self.ls_client.cancel_subscription(
                subscription["ls_subscription_id"]
            )
            if not success:
                logger.error(
                    f"Failed to cancel LS subscription: {subscription['ls_subscription_id']}"
                )
                # Continue with local cancellation anyway

        # Update subscription status
        await subscription_repo.update_subscription_status(
            subscription_id=subscription["id"],
            status="cancelled",
            cancelled_at=datetime.now(timezone.utc),
        )

        # Downgrade tenant to starter plan
        await subscription_repo.update_tenant_plan(
            tenant_id=tenant_id,
            plan="starter",
            subscription_id=None,
        )

        logger.info(f"Subscription {subscription['id']} cancelled. Reason: {reason}")
        return True, "Subscription cancelled successfully"

    async def pause_subscription(
        self,
        tenant_id: UUID,
    ) -> tuple[bool, str]:
        """Pause a subscription."""
        subscription = await subscription_repo.get_subscription_by_tenant(tenant_id)

        if not subscription:
            return False, "No active subscription found"

        if subscription["status"] != "authorized":
            return False, f"Cannot pause subscription in status: {subscription['status']}"

        # Pause in Lemon Squeezy
        if subscription.get("ls_subscription_id") and self.ls_client.is_configured:
            success = await self.ls_client.pause_subscription(
                subscription["ls_subscription_id"]
            )
            if not success:
                logger.error(
                    f"Failed to pause LS subscription: {subscription['ls_subscription_id']}"
                )

        # Update subscription status
        await subscription_repo.update_subscription_status(
            subscription_id=subscription["id"],
            status="paused",
        )

        return True, "Subscription paused successfully"

    async def process_ls_webhook(
        self,
        event_name: str,
        data: dict,
        meta: dict,
    ) -> dict:
        """
        Process webhook from Lemon Squeezy.

        Args:
            event_name: The webhook event name (e.g. subscription_created)
            data: The resource data from LS
            meta: The meta object with custom_data

        Returns:
            dict with processing result
        """
        logger.info(f"Processing LS webhook: event={event_name}")

        try:
            if event_name in ("subscription_created", "subscription_updated"):
                await self._process_subscription_event(event_name, data, meta)
            elif event_name == "subscription_cancelled":
                await self._process_subscription_cancelled(data, meta)
            elif event_name in (
                "subscription_payment_success",
                "subscription_payment_failed",
            ):
                await self._process_payment_event(event_name, data, meta)
            elif event_name == "order_created":
                await self._process_order_created(data, meta)
            else:
                logger.info(f"Unhandled LS webhook event: {event_name}")
                return {"processed": False, "message": f"Unhandled event: {event_name}"}

            return {"processed": True}

        except Exception as e:
            logger.exception(f"Error processing LS webhook: {e}")
            return {"processed": False, "message": str(e)}

    async def _process_subscription_event(
        self, event_name: str, data: dict, meta: dict
    ) -> None:
        """Process subscription_created or subscription_updated event."""
        attrs = data.get("attributes", {})
        ls_sub_id = str(data.get("id", ""))
        ls_status = attrs.get("status", "")
        custom_data = meta.get("custom_data", {})

        subscription_id_str = custom_data.get("subscription_id")
        tenant_id_str = custom_data.get("tenant_id")

        if not subscription_id_str:
            logger.warning(f"No subscription_id in LS webhook custom_data: {custom_data}")
            return

        subscription_id = UUID(subscription_id_str)

        # Map LS status to our status
        status_map = {
            "active": "authorized",
            "on_trial": "authorized",
            "paused": "paused",
            "past_due": "authorized",  # Still active, just payment issue
            "unpaid": "pending",
            "cancelled": "cancelled",
            "expired": "ended",
        }
        our_status = status_map.get(ls_status, "pending")

        # Update subscription with LS data
        await subscription_repo.update_subscription(
            subscription_id=subscription_id,
            ls_subscription_id=ls_sub_id,
            status=our_status,
            current_period_start=attrs.get("renews_at"),
            current_period_end=attrs.get("ends_at"),
        )

        # Update tenant plan if subscription is active
        if our_status == "authorized" and tenant_id_str:
            tenant_id = UUID(tenant_id_str)
            plan_type = custom_data.get("plan_type", "starter")
            await subscription_repo.update_tenant_plan(
                tenant_id=tenant_id,
                plan=plan_type,
                subscription_id=subscription_id,
            )

        logger.info(
            f"Updated subscription {subscription_id} from LS event {event_name}: "
            f"ls_status={ls_status} -> our_status={our_status}"
        )

    async def _process_subscription_cancelled(self, data: dict, meta: dict) -> None:
        """Process subscription_cancelled event."""
        custom_data = meta.get("custom_data", {})
        subscription_id_str = custom_data.get("subscription_id")
        tenant_id_str = custom_data.get("tenant_id")

        if not subscription_id_str:
            logger.warning("No subscription_id in LS cancellation webhook")
            return

        subscription_id = UUID(subscription_id_str)

        await subscription_repo.update_subscription_status(
            subscription_id=subscription_id,
            status="cancelled",
            cancelled_at=datetime.now(timezone.utc),
        )

        # Downgrade to starter
        if tenant_id_str:
            await subscription_repo.update_tenant_plan(
                tenant_id=UUID(tenant_id_str),
                plan="starter",
                subscription_id=None,
            )

        logger.info(f"Subscription {subscription_id} cancelled via LS webhook")

    async def _process_payment_event(
        self, event_name: str, data: dict, meta: dict
    ) -> None:
        """Process payment success/failure events."""
        attrs = data.get("attributes", {})
        custom_data = meta.get("custom_data", {})

        subscription_id_str = custom_data.get("subscription_id")
        tenant_id_str = custom_data.get("tenant_id")

        if not subscription_id_str or not tenant_id_str:
            logger.warning("Missing subscription_id or tenant_id in payment webhook")
            return

        subscription_id = UUID(subscription_id_str)
        tenant_id = UUID(tenant_id_str)

        ls_invoice_id = str(data.get("id", ""))
        amount = Decimal(str(attrs.get("total", 0))) / 100  # LS sends cents
        is_success = event_name == "subscription_payment_success"

        await subscription_repo.create_payment(
            tenant_id=tenant_id,
            subscription_id=subscription_id,
            ls_invoice_id=ls_invoice_id,
            amount=amount,
            currency="USD",
            status="approved" if is_success else "rejected",
            paid_at=datetime.now(timezone.utc) if is_success else None,
        )

        logger.info(
            f"Payment {'success' if is_success else 'failed'} for subscription "
            f"{subscription_id}: ${amount}"
        )

    async def _process_order_created(self, data: dict, meta: dict) -> None:
        """Process order_created event (first payment).

        Handles two scenarios:
        1. Standard web checkout: subscription_id + tenant_id in custom_data
        2. WhatsApp onboarding: pending_registration_id in custom_data
           (creates tenant from pending registration data)
        """
        attrs = data.get("attributes", {})
        custom_data = meta.get("custom_data", {})
        order_status = attrs.get("status", "")

        if order_status != "paid":
            logger.info(f"Order not paid (status={order_status}), skipping")
            return

        # Check if this is a WhatsApp onboarding payment
        pending_reg_id = custom_data.get("pending_registration_id")
        source = custom_data.get("source", "")

        if pending_reg_id and source == "whatsapp":
            await self._process_whatsapp_order(data, attrs, custom_data, pending_reg_id)
            return

        # Standard web checkout flow
        subscription_id_str = custom_data.get("subscription_id")
        tenant_id_str = custom_data.get("tenant_id")
        plan_type = custom_data.get("plan_type", "starter")

        if not subscription_id_str or not tenant_id_str:
            logger.warning("Missing IDs in order_created webhook")
            return

        subscription_id = UUID(subscription_id_str)
        tenant_id = UUID(tenant_id_str)

        await subscription_repo.update_subscription_status(
            subscription_id=subscription_id,
            status="authorized",
        )
        await subscription_repo.update_tenant_plan(
            tenant_id=tenant_id,
            plan=plan_type,
            subscription_id=subscription_id,
        )

        # Record the payment
        amount = Decimal(str(attrs.get("total", 0))) / 100
        await subscription_repo.create_payment(
            tenant_id=tenant_id,
            subscription_id=subscription_id,
            ls_invoice_id=str(data.get("id", "")),
            amount=amount,
            currency="USD",
            status="approved",
            paid_at=datetime.now(timezone.utc),
        )

        logger.info(
            f"Order created & subscription {subscription_id} activated for tenant {tenant_id}"
        )

    async def _process_whatsapp_order(
        self,
        data: dict,
        attrs: dict,
        custom_data: dict,
        pending_reg_id: str,
    ) -> None:
        """Process a paid order that originated from WhatsApp onboarding.

        Creates the tenant, user, subscription, and payment from the
        pending_registrations data.
        """
        from ..config.database import get_pool
        from ..repositories.pending_registration import get_pending_registration_repository
        from ..repositories.onboarding import get_onboarding_repository

        pending_repo = get_pending_registration_repository()
        onboarding_repo = get_onboarding_repository()

        # Look up pending registration
        pending = await pending_repo.get_by_checkout_id(None)
        # Try by ID first
        pool = await get_pool()
        pending_row = await pool.fetchrow(
            "SELECT * FROM pending_registrations WHERE id = $1 AND status = 'pending'",
            UUID(pending_reg_id),
        )

        if not pending_row:
            logger.error(f"Pending registration {pending_reg_id} not found or already completed")
            return

        pending = dict(pending_row)
        phone = pending["phone"]
        display_name = pending["display_name"]
        home_name = pending["home_name"]
        plan_type = pending["plan_type"]

        logger.info(
            f"Processing WhatsApp order for pending registration {pending_reg_id}, "
            f"phone={phone}, plan={plan_type}"
        )

        try:
            # Step 1: Create tenant
            tenant_query = """
                INSERT INTO tenants (
                    name, home_name, plan, 
                    onboarding_completed, timezone, language, currency, settings
                )
                VALUES ($1, $2, $3, true, 'America/Argentina/Buenos_Aires', 'es-AR', 'ARS', '{}'::jsonb)
                RETURNING id
            """
            tenant_id = await pool.fetchval(tenant_query, home_name, home_name, plan_type)

            # Step 2: Create user
            user_query = """
                INSERT INTO users (
                    tenant_id, phone, display_name, role,
                    phone_verified, is_active, auth_provider, created_at
                )
                VALUES ($1, $2, $3, 'owner', false, true, 'whatsapp', NOW())
                RETURNING id
            """
            user_id = await pool.fetchval(user_query, tenant_id, phone, display_name)

            # Step 3: Set owner on tenant
            await pool.execute(
                "UPDATE tenants SET owner_user_id = $1 WHERE id = $2",
                user_id, tenant_id,
            )

            # Step 4: Create default budget categories
            await onboarding_repo.create_default_budget_categories(tenant_id)

            # Step 5: Create subscription record
            subscription = await subscription_repo.create_subscription(
                tenant_id=tenant_id,
                plan_type=plan_type,
                status="authorized",
            )

            # Step 6: Link subscription to tenant
            await subscription_repo.update_tenant_plan(
                tenant_id=tenant_id,
                plan=plan_type,
                subscription_id=subscription["id"],
            )

            # Step 7: Record payment
            amount = Decimal(str(attrs.get("total", 0))) / 100
            await subscription_repo.create_payment(
                tenant_id=tenant_id,
                subscription_id=subscription["id"],
                ls_invoice_id=str(data.get("id", "")),
                amount=amount,
                currency="USD",
                status="approved",
                paid_at=datetime.now(timezone.utc),
            )

            # Step 8: Mark pending registration as completed
            await pending_repo.mark_completed(UUID(pending_reg_id))

            logger.info(
                f"WhatsApp onboarding completed via payment: "
                f"tenant={tenant_id}, user={user_id}, plan={plan_type}"
            )

        except Exception as e:
            logger.exception(
                f"Failed to process WhatsApp order for pending {pending_reg_id}: {e}"
            )

    async def sync_subscription_status(
        self,
        subscription_id: UUID,
    ) -> dict | None:
        """
        Sync subscription status with Lemon Squeezy.

        Call this to ensure local data matches LS.
        """
        subscription = await subscription_repo.get_subscription_by_id(subscription_id)
        if not subscription or not subscription.get("ls_subscription_id"):
            return subscription

        if not self.ls_client.is_configured:
            return subscription

        ls_sub = await self.ls_client.get_subscription(subscription["ls_subscription_id"])
        if not ls_sub:
            return subscription

        # Map and update status
        attrs = ls_sub.get("attributes", {})
        ls_status = attrs.get("status", "")
        status_map = {
            "active": "authorized",
            "on_trial": "authorized",
            "paused": "paused",
            "past_due": "authorized",
            "unpaid": "pending",
            "cancelled": "cancelled",
            "expired": "ended",
        }
        our_status = status_map.get(ls_status, subscription["status"])

        return await subscription_repo.update_subscription(
            subscription_id=subscription_id,
            status=our_status,
            current_period_end=attrs.get("ends_at"),
        )


# Singleton instance
_subscription_service: SubscriptionService | None = None


def get_subscription_service() -> SubscriptionService:
    """Get subscription service instance."""
    global _subscription_service
    if _subscription_service is None:
        _subscription_service = SubscriptionService()
    return _subscription_service
