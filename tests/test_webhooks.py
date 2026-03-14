from __future__ import annotations

import json
import base64
import hmac
import hashlib
from hashlib import sha256
from typing import Any
from unittest.mock import AsyncMock
from unittest.mock import Mock

import httpx
import pytest
import respx
from getpaid_simulator.core.storage import SimulatorStorage
from getpaid_simulator.core.webhooks import paynow_sign_payload
from getpaid_simulator.core.webhooks import payu_sign_payload
from getpaid_simulator.core.webhooks import WebhookDelivery


@pytest.fixture
def storage() -> SimulatorStorage:
    return SimulatorStorage()


@pytest.fixture
def webhook_delivery(storage: SimulatorStorage) -> WebhookDelivery:
    return WebhookDelivery(
        storage=storage,
        second_key="b6ca15b0d1020e8094d9b5f8d163db54",
    )


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

    def test_compute_signature_known_input(
        self, webhook_delivery: WebhookDelivery
    ):
        """Test signature computation with known input/output."""
        body = b'{"order":{"orderId":"ABC123"}}'
        second_key = "test-key"

        # SHA256(body + second_key)
        expected = sha256(body + second_key.encode()).hexdigest()

        result = webhook_delivery._compute_signature(body, second_key)

        assert result == expected

    def test_sign_payload_format(self, webhook_delivery: WebhookDelivery):
        """Test signature header format matches PayU's format."""
        body = b'{"test": "data"}'

        result = webhook_delivery._sign_payload(body)

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

    def test_signature_round_trip_verification(
        self, webhook_delivery: WebhookDelivery
    ):
        """Test that simulator signatures can be verified by PayU's algorithm."""
        body = b'{"order":{"status":"COMPLETED"}}'
        second_key = "b6ca15b0d1020e8094d9b5f8d163db54"

        # Simulator generates signature
        signed_header = webhook_delivery._sign_payload(body)

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

    headers = payu_sign_payload(body, second_key)

    assert "OpenPayU-Signature" in headers
    signature_header = headers["OpenPayU-Signature"]
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
async def test_webhook_delivery_with_custom_signer(storage: SimulatorStorage):
    captured = {"called": False, "body": b"", "key": ""}

    def custom_signer(body: bytes, key: str) -> dict[str, str]:
        captured["called"] = True
        captured["body"] = body
        captured["key"] = key
        return {"Signature": "custom-signature"}

    order_id = storage.create_order(
        {
            "provider": "paynow",
            "notifyUrl": "http://test.local/callback",
            "status": "PENDING",
            "description": "Custom signer order",
            "currencyCode": "PLN",
            "totalAmount": "10000",
            "buyer": {"email": "test@example.com"},
        }
    )

    delivery = WebhookDelivery(
        storage=storage,
        second_key="custom-key",
        sign_payload=custom_signer,
    )

    async with respx.mock:
        route = respx.post("http://test.local/callback").mock(
            return_value=httpx.Response(200)
        )

        result = await delivery.deliver_order_update(order_id)

    assert result is True
    assert captured["called"] is True
    assert captured["key"] == "custom-key"
    assert captured["body"] == route.calls.last.request.content
    assert route.calls.last.request.headers["signature"] == "custom-signature"


class TestWebhookPayloadFormat:
    """Test webhook payload structure matches PayU's OrderNotification format."""

    def test_build_order_notification_payload(
        self,
        storage: SimulatorStorage,
        webhook_delivery: WebhookDelivery,
        sample_order: str,
    ):
        """Test notification payload contains all required OrderNotification fields."""
        payload = webhook_delivery._build_order_notification(sample_order)

        # Top-level structure
        assert "order" in payload
        assert "localReceiptDateTime" in payload
        assert "properties" in payload

        order = payload["order"]

        # ReceivedOrderData fields
        assert "orderId" in order
        assert "orderCreateDate" in order
        assert "extOrderId" in order
        assert "notifyUrl" in order
        assert "customerIp" in order
        assert "merchantPosId" in order
        assert "description" in order
        assert "currencyCode" in order
        assert "totalAmount" in order
        assert "status" in order
        assert "buyer" in order
        assert "products" in order

    def test_order_notification_status_values(
        self,
        storage: SimulatorStorage,
        webhook_delivery: WebhookDelivery,
    ):
        """Test different order statuses appear correctly in notifications."""
        for status in ["COMPLETED", "CANCELED", "WAITING_FOR_CONFIRMATION"]:
            order_data = {
                "extOrderId": f"test-{status}",
                "notifyUrl": "http://test.local/callback",
                "customerIp": "127.0.0.1",
                "merchantPosId": "300746",
                "description": "Test",
                "currencyCode": "PLN",
                "totalAmount": "5000",
                "buyer": {"email": "test@example.com"},
                "products": [
                    {"name": "Test", "unitPrice": "5000", "quantity": "1"}
                ],
                "status": status,
            }
            order_id = storage.create_order(order_data)

            payload = webhook_delivery._build_order_notification(order_id)

            assert payload["order"]["status"] == status


class TestWebhookDelivery:
    """Test webhook HTTP delivery to notify_url."""

    @pytest.mark.asyncio
    async def test_deliver_to_notify_url_success(
        self,
        webhook_delivery: WebhookDelivery,
        sample_order: str,
    ):
        """Test successful webhook delivery returns 200."""
        async with respx.mock:
            route = respx.post("http://test.local/callback").mock(
                return_value=httpx.Response(200)
            )

            await webhook_delivery.deliver_order_update(sample_order)

            assert route.called
            assert route.call_count == 1

    @pytest.mark.asyncio
    async def test_deliver_includes_signature_header(
        self,
        webhook_delivery: WebhookDelivery,
        sample_order: str,
    ):
        """Test webhook request includes OpenPayU-Signature header."""
        async with respx.mock:
            route = respx.post("http://test.local/callback").mock(
                return_value=httpx.Response(200)
            )

            await webhook_delivery.deliver_order_update(sample_order)

            request = route.calls.last.request
            assert "openpayu-signature" in request.headers

            signature_header = request.headers["openpayu-signature"]
            assert signature_header.startswith("signature=")
            assert "algorithm=SHA-256" in signature_header
            assert "sender=checkout" in signature_header

    @pytest.mark.asyncio
    async def test_deliver_posts_json_body(
        self,
        webhook_delivery: WebhookDelivery,
        sample_order: str,
    ):
        """Test webhook POST contains JSON payload."""
        async with respx.mock:
            route = respx.post("http://test.local/callback").mock(
                return_value=httpx.Response(200)
            )

            await webhook_delivery.deliver_order_update(sample_order)

            request = route.calls.last.request
            assert request.headers["content-type"] == "application/json"

            body = json.loads(request.content)
            assert "order" in body
            assert body["order"]["orderId"] == sample_order

    @pytest.mark.asyncio
    async def test_signature_matches_payload(
        self,
        webhook_delivery: WebhookDelivery,
        sample_order: str,
    ):
        """Test signature header is computed from actual request body."""
        async with respx.mock:
            route = respx.post("http://test.local/callback").mock(
                return_value=httpx.Response(200)
            )

            await webhook_delivery.deliver_order_update(sample_order)

            request = route.calls.last.request
            body_bytes = request.content
            signature_header = request.headers["openpayu-signature"]

            # Extract signature from header
            parsed = dict(
                item.split("=", 1)
                for item in signature_header.split(";")
                if "=" in item
            )
            signature = parsed["signature"]

            # Recompute signature from body
            second_key = "b6ca15b0d1020e8094d9b5f8d163db54"
            expected = sha256(body_bytes + second_key.encode()).hexdigest()

            assert signature == expected


class TestWebhookRetry:
    """Test webhook retry logic on delivery failure."""

    @pytest.mark.asyncio
    async def test_retry_on_connection_error(
        self,
        webhook_delivery: WebhookDelivery,
        sample_order: str,
    ):
        """Test retry after connection failure."""
        async with respx.mock:
            route = respx.post("http://test.local/callback").mock(
                side_effect=[
                    httpx.ConnectError("Connection refused"),
                    httpx.Response(200),
                ]
            )

            result = await webhook_delivery.deliver_order_update(sample_order)

            # Should succeed after retry
            assert result is True
            assert route.call_count == 2

    @pytest.mark.asyncio
    async def test_retry_on_timeout(
        self,
        webhook_delivery: WebhookDelivery,
        sample_order: str,
    ):
        """Test retry after timeout."""
        async with respx.mock:
            route = respx.post("http://test.local/callback").mock(
                side_effect=[
                    httpx.TimeoutException("Request timeout"),
                    httpx.Response(200),
                ]
            )

            result = await webhook_delivery.deliver_order_update(sample_order)

            assert result is True
            assert route.call_count == 2

    @pytest.mark.asyncio
    async def test_retry_on_5xx_error(
        self,
        webhook_delivery: WebhookDelivery,
        sample_order: str,
    ):
        """Test retry after 5xx server error."""
        async with respx.mock:
            route = respx.post("http://test.local/callback").mock(
                side_effect=[
                    httpx.Response(500, text="Internal Server Error"),
                    httpx.Response(200),
                ]
            )

            result = await webhook_delivery.deliver_order_update(sample_order)

            assert result is True
            assert route.call_count == 2

    @pytest.mark.asyncio
    async def test_no_retry_on_4xx_error(
        self,
        webhook_delivery: WebhookDelivery,
        sample_order: str,
    ):
        """Test no retry on 4xx client error (permanent failure)."""
        async with respx.mock:
            route = respx.post("http://test.local/callback").mock(
                return_value=httpx.Response(400, text="Bad Request")
            )

            result = await webhook_delivery.deliver_order_update(sample_order)

            # Fails without retry
            assert result is False
            assert route.call_count == 1

    @pytest.mark.asyncio
    async def test_fails_after_single_retry(
        self,
        webhook_delivery: WebhookDelivery,
        sample_order: str,
    ):
        """Test delivery fails after single retry exhaustion."""
        async with respx.mock:
            route = respx.post("http://test.local/callback").mock(
                side_effect=httpx.ConnectError("Connection refused")
            )

            result = await webhook_delivery.deliver_order_update(sample_order)

            assert result is False
            # Initial attempt + 1 retry = 2 total
            assert route.call_count == 2


class TestWebhookDeliveryStatus:
    """Test webhook delivery status tracking in storage."""

    @pytest.mark.asyncio
    async def test_successful_delivery_recorded(
        self,
        storage: SimulatorStorage,
        webhook_delivery: WebhookDelivery,
        sample_order: str,
    ):
        """Test successful delivery updates order's webhook status."""
        async with respx.mock:
            respx.post("http://test.local/callback").mock(
                return_value=httpx.Response(200)
            )

            result = await webhook_delivery.deliver_order_update(sample_order)

            assert result is True

            order = storage.get_order(sample_order)
            assert order is not None
            assert "webhook_status" in order
            assert order["webhook_status"] == "success"

    @pytest.mark.asyncio
    async def test_failed_delivery_recorded(
        self,
        storage: SimulatorStorage,
        webhook_delivery: WebhookDelivery,
        sample_order: str,
    ):
        """Test failed delivery updates order's webhook status."""
        async with respx.mock:
            respx.post("http://test.local/callback").mock(
                side_effect=httpx.ConnectError("Connection refused")
            )

            result = await webhook_delivery.deliver_order_update(sample_order)

            assert result is False

            order = storage.get_order(sample_order)
            assert order is not None
            assert "webhook_status" in order
            assert order["webhook_status"] == "failed"


class TestWebhookEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_order_without_notify_url_skips_delivery(
        self,
        storage: SimulatorStorage,
        webhook_delivery: WebhookDelivery,
    ):
        """Test orders without notifyUrl don't attempt delivery."""
        order_data = {
            "extOrderId": "no-notify",
            "notifyUrl": None,
            "customerIp": "127.0.0.1",
            "merchantPosId": "300746",
            "description": "Test",
            "currencyCode": "PLN",
            "totalAmount": "1000",
            "buyer": {"email": "test@example.com"},
            "products": [
                {"name": "Test", "unitPrice": "1000", "quantity": "1"}
            ],
            "status": "COMPLETED",
        }
        order_id = storage.create_order(order_data)

        # Should return None (skipped) instead of True/False
        result = await webhook_delivery.deliver_order_update(order_id)

        assert result is None

    @pytest.mark.asyncio
    async def test_nonexistent_order_returns_none(
        self,
        webhook_delivery: WebhookDelivery,
    ):
        """Test delivery for non-existent order returns None."""
        result = await webhook_delivery.deliver_order_update("missing-order-id")

        assert result is None
