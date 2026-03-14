"""Webhook delivery system for PayU callback notifications."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC
from datetime import datetime
from hashlib import sha256
from typing import TYPE_CHECKING
from typing import Any

import httpx


if TYPE_CHECKING:
    from getpaid_simulator.core.storage import SimulatorStorage


class WebhookDelivery:
    """Handles webhook delivery to merchant notify_url with PayU signature."""

    def __init__(
        self,
        storage: SimulatorStorage,
        second_key: str = "b6ca15b0d1020e8094d9b5f8d163db54",
        timeout: float = 5.0,
        retry_delay: float = 5.0,
    ):
        """Initialize webhook delivery system.

        Args:
            storage: SimulatorStorage instance to retrieve order data
            second_key: PayU second_key for signature computation
            timeout: HTTP request timeout in seconds (default: 5.0)
            retry_delay: Delay between retry attempts in seconds (default: 5.0)
        """
        self.storage = storage
        self.second_key = second_key
        self.timeout = timeout
        self.retry_delay = retry_delay

    def _compute_signature(self, body: bytes, second_key: str) -> str:
        """Compute PayU signature: SHA256(body + second_key).

        Args:
            body: Raw request body bytes
            second_key: PayU second_key

        Returns:
            Hex-encoded SHA256 digest
        """
        return sha256(body + second_key.encode()).hexdigest()

    def _sign_payload(self, body: bytes) -> str:
        """Create OpenPayU-Signature header value.

        Args:
            body: Raw request body bytes

        Returns:
            Signature header in PayU format:
            signature=<hex>;algorithm=SHA-256;sender=checkout
        """
        sig = self._compute_signature(body, self.second_key)
        return f"signature={sig};algorithm=SHA-256;sender=checkout"

    def _build_order_notification(self, order_id: str) -> dict[str, Any]:
        """Build OrderNotification payload for webhook callback.

        Args:
            order_id: Order identifier

        Returns:
            OrderNotification dict matching PayU's callback format
        """
        order = self.storage.get_order(order_id)
        if order is None:
            return {}

        # Build ReceivedOrderData structure
        order_data: dict[str, Any] = {
            "orderId": order_id,
            "orderCreateDate": datetime.now(UTC).isoformat(),
            "extOrderId": order.get("extOrderId"),
            "notifyUrl": order.get("notifyUrl"),
            "customerIp": order.get("customerIp", "127.0.0.1"),
            "merchantPosId": order.get("merchantPosId"),
            "description": order.get("description"),
            "currencyCode": order.get("currencyCode"),
            "totalAmount": order.get("totalAmount"),
            "status": order.get("status"),
            "buyer": order.get("buyer", {}),
            "products": order.get("products", []),
        }

        # Build OrderNotification wrapper
        notification: dict[str, Any] = {
            "order": order_data,
            "localReceiptDateTime": datetime.now(UTC).isoformat(),
            "properties": None,
        }

        return notification

    async def deliver_order_update(self, order_id: str) -> bool | None:
        """Deliver webhook notification for order status update.

        Args:
            order_id: Order identifier

        Returns:
            True if delivery succeeded
            False if delivery failed (after retry)
            None if delivery skipped (no notifyUrl or order not found)
        """
        order = self.storage.get_order(order_id)
        if order is None:
            return None

        notify_url = order.get("notifyUrl")
        if not notify_url:
            return None

        # Build payload
        payload = self._build_order_notification(order_id)
        body = json.dumps(payload).encode("utf-8")

        # Sign payload
        signature_header = self._sign_payload(body)

        # Prepare request
        headers = {
            "Content-Type": "application/json",
            "OpenPayU-Signature": signature_header,
        }

        # Attempt delivery with retry logic
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for attempt in range(2):  # Initial attempt + 1 retry
                try:
                    response = await client.post(
                        notify_url,
                        content=body,
                        headers=headers,
                    )

                    # 4xx errors are permanent failures (no retry)
                    if 400 <= response.status_code < 500:
                        self.storage.update_order(
                            order_id, webhook_status="failed"
                        )
                        return False

                    # 2xx success
                    if 200 <= response.status_code < 300:
                        self.storage.update_order(
                            order_id, webhook_status="success"
                        )
                        return True

                    # 5xx errors trigger retry
                    if attempt == 0:
                        await asyncio.sleep(self.retry_delay)
                        continue

                    # Exhausted retries
                    self.storage.update_order(order_id, webhook_status="failed")
                    return False

                except (
                    httpx.ConnectError,
                    httpx.TimeoutException,
                    httpx.RequestError,
                ):
                    # Network errors trigger retry
                    if attempt == 0:
                        await asyncio.sleep(self.retry_delay)
                        continue

                    # Exhausted retries
                    self.storage.update_order(order_id, webhook_status="failed")
                    return False

        # Should never reach here
        self.storage.update_order(order_id, webhook_status="failed")
        return False
