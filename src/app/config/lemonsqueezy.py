"""Lemon Squeezy API client."""

import hashlib
import hmac
import logging
from functools import lru_cache
from typing import Any

import httpx

from .settings import get_settings

logger = logging.getLogger(__name__)

# Variant IDs for each plan (configured in Lemon Squeezy dashboard)
PLAN_VARIANT_MAP: dict[str, int] = {
    "starter": 1306485,
    "family": 1309000,
    "premium": 1309001,
}

LS_API_BASE = "https://api.lemonsqueezy.com/v1"


class LemonSqueezyClient:
    """Client for Lemon Squeezy API."""

    def __init__(self) -> None:
        settings = get_settings()
        self._api_key = settings.ls_api_key
        self._store_id = settings.ls_store_id
        self._webhook_secret = settings.ls_webhook_secret
        self._frontend_url = settings.frontend_url

        if not self._api_key:
            logger.warning("LS_API_KEY not configured - Lemon Squeezy features disabled")

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key)

    @property
    def webhook_secret(self) -> str:
        return self._webhook_secret

    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/vnd.api+json",
            "Content-Type": "application/vnd.api+json",
            "Authorization": f"Bearer {self._api_key}",
        }

    async def create_checkout(
        self,
        variant_id: int,
        email: str,
        custom_data: dict[str, Any] | None = None,
        redirect_url: str | None = None,
        custom_price: int | None = None,
        discount_code: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Create a checkout session in Lemon Squeezy.

        Args:
            variant_id: The LS variant ID for the plan
            email: Customer email to pre-fill
            custom_data: Custom data passed through to webhooks (e.g. tenant_id, subscription_id)
            redirect_url: URL to redirect after successful payment
            custom_price: Custom price in cents (overrides variant price)
            discount_code: Discount code to pre-fill

        Returns:
            LS checkout response dict with 'url' key, or None on error
        """
        if not self.is_configured:
            logger.error("Cannot create checkout: LS API key not configured")
            return None

        final_redirect = redirect_url or f"{self._frontend_url}/checkout/callback"

        checkout_data: dict[str, Any] = {"email": email}
        if custom_data:
            checkout_data["custom"] = {k: str(v) for k, v in custom_data.items()}
        if discount_code:
            checkout_data["discount_code"] = discount_code

        attributes: dict[str, Any] = {
            "checkout_data": checkout_data,
            "checkout_options": {
                "embed": False,
                "media": True,
                "logo": True,
                "desc": True,
                "discount": True,
            },
            "product_options": {
                "redirect_url": final_redirect,
                "receipt_button_text": "Ir a mi cuenta",
                "receipt_link_url": f"{self._frontend_url}/dashboard",
                "receipt_thank_you_note": "¡Gracias por suscribirte a HomeAI! Haz clic en el botón para continuar.",
            },
        }

        if custom_price is not None:
            attributes["custom_price"] = custom_price

        payload = {
            "data": {
                "type": "checkouts",
                "attributes": attributes,
                "relationships": {
                    "store": {
                        "data": {
                            "type": "stores",
                            "id": str(self._store_id),
                        }
                    },
                    "variant": {
                        "data": {
                            "type": "variants",
                            "id": str(variant_id),
                        }
                    },
                },
            }
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{LS_API_BASE}/checkouts",
                    headers=self._headers(),
                    json=payload,
                )

            if response.status_code in (200, 201):
                data = response.json()
                checkout_url = data["data"]["attributes"]["url"]
                checkout_id = data["data"]["id"]
                logger.info(f"Created LS checkout: id={checkout_id}, url={checkout_url[:80]}...")
                return {
                    "id": checkout_id,
                    "url": checkout_url,
                    "data": data,
                }
            else:
                logger.error(
                    f"Failed to create LS checkout: status={response.status_code}, "
                    f"response={response.text[:500]}"
                )
                return None

        except Exception as e:
            logger.exception(f"Error creating LS checkout: {e}")
            return None

    async def get_subscription(self, subscription_id: str) -> dict[str, Any] | None:
        """Get subscription details from Lemon Squeezy."""
        if not self.is_configured:
            return None

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    f"{LS_API_BASE}/subscriptions/{subscription_id}",
                    headers=self._headers(),
                )

            if response.status_code == 200:
                return response.json()["data"]
            return None

        except Exception as e:
            logger.exception(f"Error getting LS subscription: {e}")
            return None

    async def cancel_subscription(self, subscription_id: str) -> bool:
        """Cancel a subscription in Lemon Squeezy."""
        if not self.is_configured:
            return False

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.delete(
                    f"{LS_API_BASE}/subscriptions/{subscription_id}",
                    headers=self._headers(),
                )

            return response.status_code == 200

        except Exception as e:
            logger.exception(f"Error cancelling LS subscription: {e}")
            return False

    async def pause_subscription(self, subscription_id: str) -> bool:
        """Pause a subscription in Lemon Squeezy."""
        if not self.is_configured:
            return False

        try:
            payload = {
                "data": {
                    "type": "subscriptions",
                    "id": subscription_id,
                    "attributes": {
                        "pause": {"mode": "void"},
                    },
                }
            }

            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.patch(
                    f"{LS_API_BASE}/subscriptions/{subscription_id}",
                    headers=self._headers(),
                    json=payload,
                )

            return response.status_code == 200

        except Exception as e:
            logger.exception(f"Error pausing LS subscription: {e}")
            return False

    async def resume_subscription(self, subscription_id: str) -> bool:
        """Resume a paused subscription."""
        if not self.is_configured:
            return False

        try:
            payload = {
                "data": {
                    "type": "subscriptions",
                    "id": subscription_id,
                    "attributes": {
                        "pause": None,
                    },
                }
            }

            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.patch(
                    f"{LS_API_BASE}/subscriptions/{subscription_id}",
                    headers=self._headers(),
                    json=payload,
                )

            return response.status_code == 200

        except Exception as e:
            logger.exception(f"Error resuming LS subscription: {e}")
            return False

    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """
        Verify webhook signature from Lemon Squeezy.

        LS webhooks use HMAC-SHA256 with the webhook secret as key.
        The signature is sent in the X-Signature header.
        """
        if not self._webhook_secret:
            logger.warning("Webhook secret not configured, skipping verification")
            return True  # Allow in development

        expected = hmac.new(
            self._webhook_secret.encode(),
            payload,
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(expected, signature)


@lru_cache
def get_ls_client() -> LemonSqueezyClient:
    """Get cached Lemon Squeezy client instance."""
    return LemonSqueezyClient()
