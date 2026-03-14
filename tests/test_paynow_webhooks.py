"""Tests for PayNow webhook trigger function."""

from __future__ import annotations

import hmac
import json
from datetime import UTC
from datetime import datetime

import httpx
import pytest
import respx
from getpaid_paynow.client import PaynowClient
from getpaid_simulator.core.config import SimulatorConfig
from getpaid_simulator.core.storage import SimulatorStorage
from getpaid_simulator.providers.paynow.webhooks import trigger_paynow_webhook


@pytest.fixture
def storage() -> SimulatorStorage:
    return SimulatorStorage()


@pytest.fixture
def config() -> SimulatorConfig:
    return SimulatorConfig(
        paynow_signature_key="test-signature-key",
        paynow_notify_url="http://merchant.local/paynow/callback",
    )


@pytest.fixture
def sample_payment(storage: SimulatorStorage) -> str:
    """Create sample PayNow payment."""
    payment_data = {
        "amount": 1500,
        "currency": "PLN",
        "externalId": "PAYNOW-ORDER-WEBHOOK-42",
        "description": "PayNow test payment for webhook",
        "continueUrl": "https://example.com/continue",
        "status": "CONFIRMED",
    }
    return storage.create_order(payment_data, provider="paynow")


@pytest.mark.asyncio
async def test_trigger_paynow_webhook_sends_notification(
    storage: SimulatorStorage,
    config: SimulatorConfig,
    sample_payment: str,
):
    """Test trigger_paynow_webhook sends POST to config.paynow_notify_url."""
    async with respx.mock:
        route = respx.post("http://merchant.local/paynow/callback").mock(
            return_value=httpx.Response(200)
        )

        await trigger_paynow_webhook(sample_payment, storage, config)

        assert route.called
        assert route.call_count == 1


@pytest.mark.asyncio
async def test_paynow_webhook_body_structure(
    storage: SimulatorStorage,
    config: SimulatorConfig,
    sample_payment: str,
):
    """Test webhook body matches PayNow NotificationPayload format."""
    async with respx.mock:
        route = respx.post("http://merchant.local/paynow/callback").mock(
            return_value=httpx.Response(200)
        )

        await trigger_paynow_webhook(sample_payment, storage, config)

        request = route.calls.last.request
        body = json.loads(request.content)

        # NotificationPayload structure
        assert "paymentId" in body
        assert body["paymentId"] == sample_payment
        assert "externalId" in body
        assert body["externalId"] == "PAYNOW-ORDER-WEBHOOK-42"
        assert "status" in body
        assert body["status"] == "CONFIRMED"
        assert "modifiedAt" in body

        # modifiedAt should be ISO 8601 timestamp
        modified_at = body["modifiedAt"]
        # Should parse as valid ISO datetime
        parsed_dt = datetime.fromisoformat(modified_at.replace("Z", "+00:00"))
        assert parsed_dt.tzinfo == UTC


@pytest.mark.asyncio
async def test_paynow_webhook_signature_verifiable(
    storage: SimulatorStorage,
    config: SimulatorConfig,
    sample_payment: str,
):
    """Test webhook signature passes PayNowClient._calculate_notification_signature() verification."""
    async with respx.mock:
        route = respx.post("http://merchant.local/paynow/callback").mock(
            return_value=httpx.Response(200)
        )

        await trigger_paynow_webhook(sample_payment, storage, config)

        request = route.calls.last.request
        body_bytes = request.content
        signature_header = request.headers.get("Signature")

        assert signature_header is not None, "Signature header missing"

        # Verify signature with PayNowClient algorithm
        client = PaynowClient(
            api_key="test-api-key",
            signature_key="test-signature-key",
            api_url="http://dummy",
        )
        expected_sig = client._calculate_notification_signature(
            body_bytes.decode("utf-8")
        )

        # Use constant-time comparison
        assert hmac.compare_digest(expected_sig, signature_header)


@pytest.mark.asyncio
async def test_paynow_webhook_on_approval(
    storage: SimulatorStorage,
    config: SimulatorConfig,
):
    """Test that approving via UI triggers webhook with CONFIRMED status."""
    # This test will be implemented when we wire the webhook into routes
    # For now, we'll test the webhook function directly with CONFIRMED status
    payment_data = {
        "amount": 2500,
        "currency": "PLN",
        "externalId": "PAYNOW-APPROVAL-TEST",
        "description": "PayNow approval test",
        "continueUrl": "https://example.com/continue",
        "status": "CONFIRMED",
    }
    payment_id = storage.create_order(payment_data, provider="paynow")

    async with respx.mock:
        route = respx.post("http://merchant.local/paynow/callback").mock(
            return_value=httpx.Response(200)
        )

        await trigger_paynow_webhook(payment_id, storage, config)

        request = route.calls.last.request
        body = json.loads(request.content)

        assert body["status"] == "CONFIRMED"
        assert body["paymentId"] == payment_id
        assert body["externalId"] == "PAYNOW-APPROVAL-TEST"


@pytest.mark.asyncio
async def test_trigger_paynow_webhook_returns_none_if_no_notify_url(
    storage: SimulatorStorage,
):
    """Test webhook trigger returns None if config has no paynow_notify_url."""
    payment_data = {
        "amount": 1000,
        "currency": "PLN",
        "externalId": "NO-NOTIFY-URL",
        "description": "Payment without notify URL",
        "status": "CONFIRMED",
    }
    payment_id = storage.create_order(payment_data, provider="paynow")

    config_no_url = SimulatorConfig(paynow_notify_url="")

    result = await trigger_paynow_webhook(payment_id, storage, config_no_url)

    assert result is None


@pytest.mark.asyncio
async def test_trigger_paynow_webhook_returns_none_if_payment_not_found(
    storage: SimulatorStorage,
    config: SimulatorConfig,
):
    """Test webhook trigger returns None for nonexistent payment."""
    result = await trigger_paynow_webhook("missing-payment-id", storage, config)

    assert result is None


@pytest.mark.asyncio
async def test_trigger_paynow_webhook_retries_on_5xx(
    storage: SimulatorStorage,
    config: SimulatorConfig,
    sample_payment: str,
):
    """Test webhook retries on 5xx server errors."""
    async with respx.mock:
        route = respx.post("http://merchant.local/paynow/callback").mock(
            side_effect=[
                httpx.Response(503, text="Service Unavailable"),
                httpx.Response(200),
            ]
        )

        await trigger_paynow_webhook(sample_payment, storage, config)

        assert route.call_count == 2


@pytest.mark.asyncio
async def test_trigger_paynow_webhook_no_retry_on_4xx(
    storage: SimulatorStorage,
    config: SimulatorConfig,
    sample_payment: str,
):
    """Test webhook does not retry on 4xx client errors."""
    async with respx.mock:
        route = respx.post("http://merchant.local/paynow/callback").mock(
            return_value=httpx.Response(400, text="Bad Request")
        )

        await trigger_paynow_webhook(sample_payment, storage, config)

        assert route.call_count == 1
