"""Subscription service for business logic and Mercado Pago integration."""

import logging
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from ..config.mercadopago import get_mp_client
from ..repositories import coupon_repo, plan_pricing_repo, subscription_repo
from ..schemas.subscription import (
    SubscriptionCreateResponse,
    SubscriptionStatusResponse,
    WebhookPayload,
    WebhookResponse,
)

logger = logging.getLogger(__name__)


class SubscriptionService:
    """Service for managing subscriptions with Mercado Pago."""

    def __init__(self) -> None:
        self.mp_client = get_mp_client()

    async def create_subscription(
        self,
        tenant_id: UUID,
        plan_type: str,
        payer_email: str,
        coupon_code: str | None = None,
        back_url: str | None = None,
    ) -> SubscriptionCreateResponse:
        """
        Create a new subscription for a tenant.
        
        Args:
            tenant_id: The tenant ID
            plan_type: Plan type (family or premium)
            payer_email: Payer's email for MP
            coupon_code: Optional coupon code for discount
            back_url: URL to redirect after payment
            
        Returns:
            SubscriptionCreateResponse with checkout URL and pricing
        """
        # Validate plan type
        if plan_type not in ("family", "premium"):
            raise ValueError(f"Invalid plan type: {plan_type}")

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

        # Create MP subscription (inline preapproval) if configured
        if self.mp_client.is_configured:
            preapproval = self.mp_client.create_subscription(
                reason=f"HomeAI {plan['name']}",
                price=float(final_price),
                payer_email=payer_email,
                external_reference=str(subscription["id"]),
                currency=plan.get("currency", "ARS"),
                back_url=back_url,
            )

            if preapproval:
                # Update subscription with MP data
                await subscription_repo.update_subscription(
                    subscription_id=subscription["id"],
                    mp_preapproval_id=preapproval["id"],
                    mp_payer_id=preapproval.get("payer_id"),
                )
                checkout_url = preapproval.get("init_point")

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

        # Cancel in MP if we have a preapproval ID
        if subscription.get("mp_preapproval_id") and self.mp_client.is_configured:
            success = self.mp_client.cancel_preapproval(subscription["mp_preapproval_id"])
            if not success:
                logger.error(f"Failed to cancel MP preapproval: {subscription['mp_preapproval_id']}")
                # Continue with local cancellation anyway

        # Update subscription status
        await subscription_repo.update_subscription_status(
            subscription_id=subscription["id"],
            status="cancelled",
            cancelled_at=datetime.utcnow(),
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

        # Pause in MP
        if subscription.get("mp_preapproval_id") and self.mp_client.is_configured:
            success = self.mp_client.pause_preapproval(subscription["mp_preapproval_id"])
            if not success:
                logger.error(f"Failed to pause MP preapproval: {subscription['mp_preapproval_id']}")

        # Update subscription status
        await subscription_repo.update_subscription_status(
            subscription_id=subscription["id"],
            status="paused",
        )

        return True, "Subscription paused successfully"

    async def process_webhook(
        self,
        payload: WebhookPayload,
        x_signature: str | None = None,
        x_request_id: str | None = None,
    ) -> WebhookResponse:
        """
        Process webhook from Mercado Pago.
        
        Args:
            payload: Webhook payload
            x_signature: Signature header for validation
            x_request_id: Request ID header
            
        Returns:
            WebhookResponse
        """
        logger.info(f"Processing webhook: action={payload.action}, type={payload.type}")

        # Verify signature if we have webhook secret configured
        if x_signature and x_request_id and self.mp_client.webhook_secret:
            is_valid = self.mp_client.verify_webhook_signature(
                x_signature=x_signature,
                x_request_id=x_request_id,
                data_id=payload.data.id,
            )
            if not is_valid:
                logger.warning("Invalid webhook signature")
                return WebhookResponse(received=True, processed=False, message="Invalid signature")

        try:
            if payload.type == "subscription_preapproval":
                await self._process_preapproval_webhook(payload)
            elif payload.type == "payment":
                await self._process_payment_webhook(payload)
            else:
                logger.info(f"Unhandled webhook type: {payload.type}")
                return WebhookResponse(received=True, processed=False, message="Unhandled type")

            return WebhookResponse(received=True, processed=True)

        except Exception as e:
            logger.exception(f"Error processing webhook: {e}")
            return WebhookResponse(received=True, processed=False, message=str(e))

    async def _process_preapproval_webhook(self, payload: WebhookPayload) -> None:
        """Process subscription preapproval webhook."""
        if not self.mp_client.is_configured:
            return

        # Get preapproval details from MP
        preapproval = self.mp_client.get_preapproval(payload.data.id)
        if not preapproval:
            logger.error(f"Could not fetch preapproval: {payload.data.id}")
            return

        # Find our subscription
        subscription = await subscription_repo.get_subscription_by_mp_id(payload.data.id)
        if not subscription:
            logger.warning(f"Subscription not found for preapproval: {payload.data.id}")
            return

        # Map MP status to our status
        mp_status = preapproval.get("status", "").lower()
        status_map = {
            "authorized": "authorized",
            "pending": "pending",
            "paused": "paused",
            "cancelled": "cancelled",
        }
        our_status = status_map.get(mp_status, subscription["status"])

        # Update subscription
        await subscription_repo.update_subscription(
            subscription_id=subscription["id"],
            status=our_status,
            current_period_start=preapproval.get("date_created"),
            current_period_end=preapproval.get("next_payment_date"),
            mp_payer_id=preapproval.get("payer_id"),
        )

        # Update tenant plan if authorized
        if our_status == "authorized":
            await subscription_repo.update_tenant_plan(
                tenant_id=subscription["tenant_id"],
                plan=subscription["plan_type"],
                subscription_id=subscription["id"],
            )

        logger.info(f"Updated subscription {subscription['id']} to status: {our_status}")

    async def _process_payment_webhook(self, payload: WebhookPayload) -> None:
        """Process payment webhook."""
        if not self.mp_client.is_configured:
            return

        # Check if we already processed this payment
        existing = await subscription_repo.get_payment_by_mp_id(payload.data.id)
        if existing:
            logger.info(f"Payment already processed: {payload.data.id}")
            return

        # Get payment details from MP
        payment = self.mp_client.get_payment(payload.data.id)
        if not payment:
            logger.error(f"Could not fetch payment: {payload.data.id}")
            return

        # Find subscription by external reference
        external_ref = payment.get("external_reference")
        if not external_ref:
            logger.warning(f"Payment {payload.data.id} has no external_reference")
            return

        subscription = await subscription_repo.get_subscription_by_id(UUID(external_ref))
        if not subscription:
            logger.warning(f"Subscription not found: {external_ref}")
            return

        # Create payment record
        status_map = {
            "approved": "approved",
            "pending": "pending",
            "rejected": "rejected",
            "refunded": "refunded",
        }
        payment_status = status_map.get(payment.get("status", ""), "pending")

        await subscription_repo.create_payment(
            tenant_id=subscription["tenant_id"],
            subscription_id=subscription["id"],
            mp_payment_id=payload.data.id,
            amount=Decimal(str(payment.get("transaction_amount", 0))),
            currency=payment.get("currency_id", "ARS"),
            status=payment_status,
            paid_at=datetime.utcnow() if payment_status == "approved" else None,
        )

        # Update subscription status if payment approved
        if payment_status == "approved" and subscription["status"] == "pending":
            await subscription_repo.update_subscription_status(
                subscription_id=subscription["id"],
                status="authorized",
            )
            
            # Update tenant plan
            await subscription_repo.update_tenant_plan(
                tenant_id=subscription["tenant_id"],
                plan=subscription["plan_type"],
                subscription_id=subscription["id"],
            )

        logger.info(f"Processed payment {payload.data.id} for subscription {subscription['id']}")

    async def sync_subscription_status(
        self,
        subscription_id: UUID,
    ) -> dict | None:
        """
        Sync subscription status with Mercado Pago.
        
        Call this to ensure local data matches MP.
        """
        subscription = await subscription_repo.get_subscription_by_id(subscription_id)
        if not subscription or not subscription.get("mp_preapproval_id"):
            return subscription

        if not self.mp_client.is_configured:
            return subscription

        preapproval = self.mp_client.get_preapproval(subscription["mp_preapproval_id"])
        if not preapproval:
            return subscription

        # Map and update status
        mp_status = preapproval.get("status", "").lower()
        status_map = {
            "authorized": "authorized",
            "pending": "pending",
            "paused": "paused",
            "cancelled": "cancelled",
        }
        our_status = status_map.get(mp_status, subscription["status"])

        return await subscription_repo.update_subscription(
            subscription_id=subscription_id,
            status=our_status,
            current_period_end=preapproval.get("next_payment_date"),
        )


# Singleton instance
_subscription_service: SubscriptionService | None = None


def get_subscription_service() -> SubscriptionService:
    """Get subscription service instance."""
    global _subscription_service
    if _subscription_service is None:
        _subscription_service = SubscriptionService()
    return _subscription_service
