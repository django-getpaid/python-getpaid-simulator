"""Tests for PayU webhook trigger function."""

from __future__ import annotations

import json
from hashlib import sha256

import httpx
import pytest
import respx
from getpaid_payu.simulator.webhooks import trigger_payu_webhook

from getpaid_simulator.core.storage import SimulatorStorage
from getpaid_simulator.core.webhooks import WebhookTransport


@pytest.fixture
def storage() -> SimulatorStorage:
    return SimulatorStorage()


@pytest.fixture
def provider_config() -> dict[str, str]:
    return {"second_key": "test-second-key"}


@pytest.fixture
def webhook_transport() -> WebhookTransport:
    return WebhookTransport(timeout=5.0, retry_delay=0.0, max_retries=1)


@pytest.fixture
def sample_order(storage: SimulatorStorage) -> str:
    """Create sample PayU order."""
    order_data = {
        "extOrderId": "ORDER-WEBHOOK-TEST",
        "notifyUrl": "http://merchant.local/payu/callback",
        "customerIp": "127.0.0.1",
        "merchantPosId": "145227",
        "description": "Test order for webhook",
        "currencyCode": "PLN",
        "totalAmount": "15000",
        "buyer": {
            "email": "webhook@example.com",
            "phone": "+48123456789",
            "firstName": "Jan",
            "lastName": "Kowalski",
        },
        "products": [
            {
                "name": "Webhook test product",
                "unitPrice": "15000",
                "quantity": "1",
            }
        ],
        "status": "COMPLETED",
    }
    return storage.create_order(order_data, provider="payu")


@pytest.mark.asyncio
async def test_trigger_payu_webhook_sends_notification(
    storage: SimulatorStorage,
    provider_config: dict[str, str],
    webhook_transport: WebhookTransport,
    sample_order: str,
):
    """Test trigger_payu_webhook sends POST to notifyUrl."""
    async with respx.mock:
        route = respx.post("http://merchant.local/payu/callback").mock(
            return_value=httpx.Response(200)
        )

        result = await trigger_payu_webhook(
            sample_order,
            storage,
            provider_config,
            webhook_transport,
        )

        assert result is True
        assert route.called
        assert route.call_count == 1


@pytest.mark.asyncio
async def test_trigger_payu_webhook_includes_signature_header(
    storage: SimulatorStorage,
    provider_config: dict[str, str],
    webhook_transport: WebhookTransport,
    sample_order: str,
):
    """Test webhook includes OpenPayU-Signature header."""
    async with respx.mock:
        route = respx.post("http://merchant.local/payu/callback").mock(
            return_value=httpx.Response(200)
        )

        await trigger_payu_webhook(
            sample_order,
            storage,
            provider_config,
            webhook_transport,
        )

        request = route.calls.last.request
        assert "openpayu-signature" in request.headers

        signature_header = request.headers["openpayu-signature"]
        assert signature_header.startswith("signature=")
        assert "algorithm=SHA-256" in signature_header
        assert "sender=checkout" in signature_header


@pytest.mark.asyncio
async def test_trigger_payu_webhook_body_structure(
    storage: SimulatorStorage,
    provider_config: dict[str, str],
    webhook_transport: WebhookTransport,
    sample_order: str,
):
    """Test webhook body matches PayU OrderNotification format."""
    async with respx.mock:
        route = respx.post("http://merchant.local/payu/callback").mock(
            return_value=httpx.Response(200)
        )

        await trigger_payu_webhook(
            sample_order,
            storage,
            provider_config,
            webhook_transport,
        )

        request = route.calls.last.request
        body = json.loads(request.content)

        # Top-level OrderNotification structure
        assert "order" in body
        assert "localReceiptDateTime" in body
        assert "properties" in body

        # ReceivedOrderData structure
        order = body["order"]
        assert "orderId" in order
        assert order["orderId"] == sample_order
        assert "extOrderId" in order
        assert order["extOrderId"] == "ORDER-WEBHOOK-TEST"
        assert "orderCreateDate" in order
        assert "notifyUrl" in order
        assert "customerIp" in order
        assert "merchantPosId" in order
        assert "description" in order
        assert "currencyCode" in order
        assert "totalAmount" in order
        assert order["totalAmount"] == "15000"
        assert "status" in order
        assert order["status"] == "COMPLETED"
        assert "buyer" in order
        assert "products" in order


@pytest.mark.asyncio
async def test_trigger_payu_webhook_signature_verification(
    storage: SimulatorStorage,
    provider_config: dict[str, str],
    webhook_transport: WebhookTransport,
    sample_order: str,
):
    """Test webhook signature can be verified with PayU algorithm."""
    async with respx.mock:
        route = respx.post("http://merchant.local/payu/callback").mock(
            return_value=httpx.Response(200)
        )

        await trigger_payu_webhook(
            sample_order,
            storage,
            provider_config,
            webhook_transport,
        )

        request = route.calls.last.request
        body_bytes = request.content
        signature_header = request.headers["openpayu-signature"]

        # Extract signature
        parsed = dict(
            item.split("=", 1)
            for item in signature_header.split(";")
            if "=" in item
        )
        signature = parsed["signature"]

        # Verify signature matches PayU algorithm
        expected = sha256(body_bytes + b"test-second-key").hexdigest()
        assert signature == expected


@pytest.mark.asyncio
async def test_trigger_payu_webhook_returns_none_if_no_notify_url(
    storage: SimulatorStorage,
    provider_config: dict[str, str],
    webhook_transport: WebhookTransport,
):
    """Test webhook trigger returns None if order has no notifyUrl."""
    order_data = {
        "extOrderId": "NO-NOTIFY-URL",
        "notifyUrl": None,
        "customerIp": "127.0.0.1",
        "merchantPosId": "145227",
        "description": "Order without notify URL",
        "currencyCode": "PLN",
        "totalAmount": "5000",
        "buyer": {"email": "test@example.com"},
        "products": [{"name": "Test", "unitPrice": "5000", "quantity": "1"}],
        "status": "COMPLETED",
    }
    order_id = storage.create_order(order_data, provider="payu")

    result = await trigger_payu_webhook(
        order_id,
        storage,
        provider_config,
        webhook_transport,
    )

    assert result is None


@pytest.mark.asyncio
async def test_trigger_payu_webhook_returns_none_if_order_not_found(
    storage: SimulatorStorage,
    provider_config: dict[str, str],
    webhook_transport: WebhookTransport,
):
    """Test webhook trigger returns None for nonexistent order."""
    result = await trigger_payu_webhook(
        "missing-order-id",
        storage,
        provider_config,
        webhook_transport,
    )

    assert result is None


@pytest.mark.asyncio
async def test_trigger_payu_webhook_retries_on_5xx(
    storage: SimulatorStorage,
    provider_config: dict[str, str],
    webhook_transport: WebhookTransport,
    sample_order: str,
):
    """Test webhook retries on 5xx server errors."""
    async with respx.mock:
        route = respx.post("http://merchant.local/payu/callback").mock(
            side_effect=[
                httpx.Response(503, text="Service Unavailable"),
                httpx.Response(200),
            ]
        )

        result = await trigger_payu_webhook(
            sample_order,
            storage,
            provider_config,
            webhook_transport,
        )

        assert result is True
        assert route.call_count == 2


@pytest.mark.asyncio
async def test_trigger_payu_webhook_no_retry_on_4xx(
    storage: SimulatorStorage,
    provider_config: dict[str, str],
    webhook_transport: WebhookTransport,
    sample_order: str,
):
    """Test webhook does not retry on 4xx client errors."""
    async with respx.mock:
        route = respx.post("http://merchant.local/payu/callback").mock(
            return_value=httpx.Response(400, text="Bad Request")
        )

        result = await trigger_payu_webhook(
            sample_order,
            storage,
            provider_config,
            webhook_transport,
        )

        assert result is False
        assert route.call_count == 1
