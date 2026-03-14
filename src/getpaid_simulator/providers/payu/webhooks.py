"""PayU webhook trigger functionality."""

from __future__ import annotations

from typing import TYPE_CHECKING

from getpaid_simulator.core.webhooks import WebhookDelivery
from getpaid_simulator.core.webhooks import payu_sign_payload


if TYPE_CHECKING:
    from getpaid_simulator.core.storage import SimulatorStorage
    from getpaid_simulator.core.config import SimulatorConfig


async def trigger_payu_webhook(
    order_id: str,
    storage: SimulatorStorage,
    config: SimulatorConfig,
) -> bool | None:
    """Trigger PayU webhook notification for an order.

    Args:
        order_id: Order identifier
        storage: SimulatorStorage instance
        config: SimulatorConfig instance containing payu_second_key

    Returns:
        True if webhook delivered successfully
        False if delivery failed
        None if delivery skipped (no notifyUrl or order not found)
    """
    delivery = WebhookDelivery(
        storage=storage,
        sign_payload=payu_sign_payload,
        second_key=config.payu_second_key,
        timeout=config.webhook_timeout,
    )

    return await delivery.deliver_order_update(order_id)
