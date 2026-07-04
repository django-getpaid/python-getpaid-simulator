from __future__ import annotations

import base64
import hashlib
import hmac
from hashlib import sha256

import httpx
import pytest
import respx
from getpaid_paynow.simulator.signing import sign_webhook as paynow_sign_payload
from getpaid_payu.simulator.signing import compute_signature
from getpaid_payu.simulator.signing import sign_payload

from getpaid_simulator.core.storage import SimulatorStorage
from getpaid_simulator.core.webhooks import WebhookTransport


@pytest.fixture
def storage() -> SimulatorStorage:
    return SimulatorStorage()


@pytest.fixture
def webhook_transport() -> WebhookTransport:
    return WebhookTransport(timeout=5.0, retry_delay=0.0, max_retries=1)


@pytest.fixture
def sample_order(storage: SimulatorStorage) -> str:
    """Create a sample order and return its ID."""
    order_data = {
        "extOrderId": "test-ext-123",
        "notifyUrl": "http://test.local/callback",
        "customerIp": "127.0.0.1",
        "merchantPosId": "300746",
        "description": "Test payment",
        "currencyCode": "PLN",
        "totalAmount": "10000",
        "buyer": {
            "email": "test@example.com",
            "phone": "+48123456789",
            "firstName": "Jan",
            "lastName": "Kowalski",
        },
        "products": [
            {
                "name": "Test product",
                "unitPrice": "10000",
                "quantity": "1",
            }
        ],
        "status": "NEW",
    }
    order_id = storage.create_order(order_data)
    storage.update_order(order_id, status="COMPLETED")
    return order_id


class TestWebhookSignature:
    """Test webhook signature generation matching PayU's scheme."""

    def test_compute_signature_known_input(self):
        """Test signature computation with known input/output."""
        body = b'{"order":{"orderId":"ABC123"}}'
        second_key = "test-key"

        # SHA256(body + second_key)
        expected = sha256(body + second_key.encode()).hexdigest()

        result = compute_signature(body, second_key)

        assert result == expected

    def test_sign_payload_format(self):
        """Test signature header format matches PayU's format."""
        body = b'{"test": "data"}'

        result = sign_payload(body, "b6ca15b0d1020e8094d9b5f8d163db54")

        # Expected format: signature=<hex>;algorithm=SHA-256;sender=checkout
        assert result.startswith("signature=")
        assert ";algorithm=SHA-256;" in result
        assert result.endswith(";sender=checkout")

        # Extract signature part
        signature_part = result.split(";")[0]
        signature_value = signature_part.split("=")[1]

        # Should be 64 hex characters (SHA256)
        assert len(signature_value) == 64
        assert all(c in "0123456789abcdef" for c in signature_value)

    def test_signature_round_trip_verification(self):
        """Simulator signatures verify with PayU's own algorithm."""
        body = b'{"order":{"status":"COMPLETED"}}'
        second_key = "b6ca15b0d1020e8094d9b5f8d163db54"

        # Simulator generates signature
        signed_header = sign_payload(body, second_key)

        # Extract signature from header
        parsed = dict(
            item.split("=", 1)
            for item in signed_header.split(";")
            if "=" in item
        )
        signature = parsed["signature"]

        # PayU processor verification algorithm
        expected = sha256(body + second_key.encode()).hexdigest()

        assert signature == expected


def test_payu_sign_payload_returns_openpayu_signature_header():
    body = b'{"order":{"status":"COMPLETED"}}'
    second_key = "b6ca15b0d1020e8094d9b5f8d163db54"

    signature_header = sign_payload(body, second_key)
    assert signature_header.startswith("signature=")
    assert ";algorithm=SHA-256;" in signature_header
    assert signature_header.endswith(";sender=checkout")


def test_paynow_sign_payload():
    body = b'{"paymentId":"123","status":"CONFIRMED"}'
    key = "test-key"

    headers = paynow_sign_payload(body, key)

    assert set(headers.keys()) == {"Signature"}
    expected_signature = base64.b64encode(
        hmac.new(key.encode(), body, hashlib.sha256).digest()
    ).decode()
    assert headers["Signature"] == expected_signature


@pytest.mark.asyncio
async def test_webhook_transport_retries_on_5xx(
    webhook_transport: WebhookTransport,
):
    async with respx.mock:
        route = respx.post("http://test.local/callback").mock(
            side_effect=[httpx.Response(503), httpx.Response(200)]
        )

        result = await webhook_transport.deliver(
            url="http://test.local/callback",
            body=b"{}",
            headers={"Content-Type": "application/json"},
        )

    assert result is True
    assert route.call_count == 2


@pytest.mark.asyncio
async def test_webhook_transport_does_not_retry_on_4xx(
    webhook_transport: WebhookTransport,
):
    async with respx.mock:
        route = respx.post("http://test.local/callback").mock(
            return_value=httpx.Response(400)
        )

        result = await webhook_transport.deliver(
            url="http://test.local/callback",
            body=b"{}",
            headers={"Content-Type": "application/json"},
        )

    assert result is False
    assert route.call_count == 1
