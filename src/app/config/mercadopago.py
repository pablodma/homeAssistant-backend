"""Mercado Pago SDK configuration."""

import logging
from functools import lru_cache
from typing import Any

import mercadopago

from .settings import get_settings

logger = logging.getLogger(__name__)


class MercadoPagoClient:
    """Wrapper for Mercado Pago SDK with configuration management."""

    def __init__(self) -> None:
        """Initialize Mercado Pago SDK with access token from settings."""
        settings = get_settings()
        self._access_token = settings.mp_access_token
        self._public_key = settings.mp_public_key
        self._webhook_secret = settings.mp_webhook_secret
        self._sandbox = settings.mp_sandbox
        
        if not self._access_token:
            logger.warning("MP_ACCESS_TOKEN not configured - Mercado Pago features disabled")
            self._sdk = None
        else:
            self._sdk = mercadopago.SDK(self._access_token)
            logger.info(f"Mercado Pago SDK initialized (sandbox={self._sandbox})")

    @property
    def sdk(self) -> mercadopago.SDK | None:
        """Get the Mercado Pago SDK instance."""
        return self._sdk

    @property
    def public_key(self) -> str:
        """Get the public key for frontend."""
        return self._public_key

    @property
    def webhook_secret(self) -> str:
        """Get the webhook secret for signature validation."""
        return self._webhook_secret

    @property
    def is_sandbox(self) -> bool:
        """Check if running in sandbox mode."""
        return self._sandbox

    @property
    def is_configured(self) -> bool:
        """Check if Mercado Pago is properly configured."""
        return self._sdk is not None

    def create_preapproval_plan(
        self,
        plan_type: str,
        price: float,
        currency: str = "ARS",
        reason: str = "HomeAI Subscription",
    ) -> dict[str, Any] | None:
        """
        Create a subscription plan in Mercado Pago.
        
        Args:
            plan_type: Plan identifier (family, premium)
            price: Monthly price
            currency: Currency code (default: ARS)
            reason: Description of the subscription
            
        Returns:
            MP response dict with plan_id or None on error
        """
        if not self._sdk:
            logger.error("Cannot create plan: MP SDK not configured")
            return None

        plan_data = {
            "reason": f"{reason} - {plan_type.title()}",
            "auto_recurring": {
                "frequency": 1,
                "frequency_type": "months",
                "transaction_amount": price,
                "currency_id": currency,
            },
            "back_url": f"https://homeai.app/checkout/callback",
        }

        try:
            result = self._sdk.preapproval_plan().create(plan_data)
            if result["status"] == 201:
                logger.info(f"Created MP plan: {result['response']['id']}")
                return result["response"]
            else:
                logger.error(f"Failed to create MP plan: {result}")
                return None
        except Exception as e:
            logger.exception(f"Error creating MP plan: {e}")
            return None

    def create_preapproval(
        self,
        plan_id: str,
        payer_email: str,
        external_reference: str,
        back_url: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Create a subscription (preapproval) for a payer.
        
        Args:
            plan_id: The MP plan ID
            payer_email: Payer's email
            external_reference: Our internal reference (tenant_id)
            back_url: URL to redirect after payment
            
        Returns:
            MP response with init_point URL or None on error
        """
        if not self._sdk:
            logger.error("Cannot create preapproval: MP SDK not configured")
            return None

        preapproval_data = {
            "preapproval_plan_id": plan_id,
            "payer_email": payer_email,
            "external_reference": external_reference,
            "status": "pending",
        }
        
        if back_url:
            preapproval_data["back_url"] = back_url

        try:
            result = self._sdk.preapproval().create(preapproval_data)
            if result["status"] == 201:
                logger.info(f"Created MP preapproval: {result['response']['id']}")
                return result["response"]
            else:
                logger.error(f"Failed to create MP preapproval: {result}")
                return None
        except Exception as e:
            logger.exception(f"Error creating MP preapproval: {e}")
            return None

    def get_preapproval(self, preapproval_id: str) -> dict[str, Any] | None:
        """Get preapproval details by ID."""
        if not self._sdk:
            return None

        try:
            result = self._sdk.preapproval().get(preapproval_id)
            if result["status"] == 200:
                return result["response"]
            return None
        except Exception as e:
            logger.exception(f"Error getting preapproval: {e}")
            return None

    def cancel_preapproval(self, preapproval_id: str) -> bool:
        """Cancel a preapproval (subscription)."""
        if not self._sdk:
            return False

        try:
            result = self._sdk.preapproval().update(
                preapproval_id, 
                {"status": "cancelled"}
            )
            return result["status"] == 200
        except Exception as e:
            logger.exception(f"Error cancelling preapproval: {e}")
            return False

    def pause_preapproval(self, preapproval_id: str) -> bool:
        """Pause a preapproval (subscription)."""
        if not self._sdk:
            return False

        try:
            result = self._sdk.preapproval().update(
                preapproval_id,
                {"status": "paused"}
            )
            return result["status"] == 200
        except Exception as e:
            logger.exception(f"Error pausing preapproval: {e}")
            return False

    def get_payment(self, payment_id: str) -> dict[str, Any] | None:
        """Get payment details by ID."""
        if not self._sdk:
            return None

        try:
            result = self._sdk.payment().get(payment_id)
            if result["status"] == 200:
                return result["response"]
            return None
        except Exception as e:
            logger.exception(f"Error getting payment: {e}")
            return None

    def verify_webhook_signature(
        self,
        x_signature: str,
        x_request_id: str,
        data_id: str,
    ) -> bool:
        """
        Verify webhook signature from Mercado Pago.
        
        Args:
            x_signature: Value from x-signature header
            x_request_id: Value from x-request-id header
            data_id: The data.id from webhook payload
            
        Returns:
            True if signature is valid
        """
        if not self._webhook_secret:
            logger.warning("Webhook secret not configured, skipping verification")
            return True  # Allow in development

        import hashlib
        import hmac

        # Parse x-signature header
        parts = {}
        for part in x_signature.split(","):
            key, value = part.split("=", 1)
            parts[key.strip()] = value.strip()

        ts = parts.get("ts", "")
        v1 = parts.get("v1", "")

        if not ts or not v1:
            logger.error("Invalid x-signature format")
            return False

        # Build manifest string
        manifest = f"id:{data_id};request-id:{x_request_id};ts:{ts};"

        # Generate HMAC
        expected_signature = hmac.new(
            self._webhook_secret.encode(),
            manifest.encode(),
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(v1, expected_signature)


@lru_cache
def get_mp_client() -> MercadoPagoClient:
    """Get cached Mercado Pago client instance."""
    return MercadoPagoClient()
