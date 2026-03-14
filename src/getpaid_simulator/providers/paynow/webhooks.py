"""PayNow webhook trigger functionality."""

from __future__ import annotations

import json
from datetime import UTC
from datetime import datetime
from typing import TYPE_CHECKING

import httpx

from getpaid_simulator.providers.paynow.signing import (
    calculate_notification_signature,
)

if TYPE_CHECKING:
    from getpaid_simulator.core.config import SimulatorConfig
    from getpaid_simulator.core.storage import SimulatorStorage


async def trigger_paynow_webhook(
    payment_id: str,
    storage: SimulatorStorage,
    config: SimulatorConfig,
) -> bool | None:
    """Trigger PayNow webhook notification for a payment.

    Sends a POST request to config.paynow_notify_url with NotificationPayload
    body matching the PayNow V3 API contract. The body is signed using
    HMAC-SHA256 base64 signature in the Signature header.

    Args:
        payment_id: Payment identifier
        storage: SimulatorStorage instance
        config: SimulatorConfig instance containing paynow_notify_url and paynow_signature_key

    Returns:
        True if webhook delivered successfully
        False if delivery failed
        None if delivery skipped (no notify_url or payment not found)
    """
    # Check if notify URL is configured
    if not config.paynow_notify_url:
        return None

    # Fetch payment from storage
    payment = storage.get_order(payment_id)
    if not payment:
        return None

    # Build NotificationPayload body
    notification_body = {
        "paymentId": payment_id,
        "externalId": payment.get("externalId", ""),
        "status": payment.get("status", "NEW"),
        "modifiedAt": datetime.now(UTC).isoformat(),
    }

    # Serialize to compact JSON (no extra whitespace)
    body_json = json.dumps(notification_body, separators=(",", ":"))

    # Sign the body with HMAC-SHA256 base64
    signature = calculate_notification_signature(
        body_json, config.paynow_signature_key
    )

    # Prepare headers
    headers = {"Signature": signature, "Content-Type": "application/json"}

    # POST to notify URL with retry logic
    max_retries = 1
    async with httpx.AsyncClient(timeout=config.webhook_timeout) as client:
        for attempt in range(max_retries + 1):
            try:
                response = await client.post(
                    config.paynow_notify_url,
                    content=body_json,
                    headers=headers,
                )
                response.raise_for_status()
                return True
            except httpx.HTTPStatusError as e:
                # Retry on 5xx, fail on 4xx
                if e.response.status_code >= 500 and attempt < max_retries:
                    continue
                return False
            except httpx.RequestError:
                # Network error - retry if attempts remaining
                if attempt < max_retries:
                    continue
                return False

    return False
