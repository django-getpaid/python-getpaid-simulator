"""Test PayNow signature signing module.

TDD: Tests written FIRST before implementation.
Cross-verify: Must match real PaynowClient signature output.
"""

import base64
import hashlib
import hmac
import json


def test_calculate_notification_signature():
    """Test notification signature calculation matches PayNow algorithm.

    Algorithm (from getpaid-paynow/client.py:104):
    - HMAC-SHA256(body.encode(), signature_key.encode())
    - base64 encode result
    """
    from getpaid_paynow.simulator.signing import (
        calculate_notification_signature,
    )

    signature_key = "test-signature-key-123"
    body = '{"orderId":"ABC123","status":"CONFIRMED"}'

    # Expected: base64(HMAC-SHA256(body, key))
    expected = base64.b64encode(
        hmac.new(
            signature_key.encode("utf-8"),
            body.encode("utf-8"),
            hashlib.sha256,
        ).digest()
    ).decode("utf-8")

    result = calculate_notification_signature(body, signature_key)

    assert result == expected
    assert isinstance(result, str)


def test_calculate_notification_signature_matches_real_client():
    """Cross-verify: simulator signature MUST match real PaynowClient output.

    CRITICAL: This test verifies byte-identical output for identical inputs.
    """
    import pathlib

    # Import real client implementation for cross-verification
    import sys

    from getpaid_paynow.simulator.signing import (
        calculate_notification_signature,
    )

    client_path = (
        pathlib.Path(__file__).parent.parent.parent / "getpaid-paynow" / "src"
    )
    sys.path.insert(0, str(client_path))

    try:
        from getpaid_paynow.client import PaynowClient

        signature_key = "real-key-789"
        body = '{"orderId":"XYZ999","status":"PENDING"}'

        # Real client signature
        client = PaynowClient(
            api_key="dummy",
            signature_key=signature_key,
            api_url="http://dummy",
        )
        real_signature = client._calculate_notification_signature(body)

        # Simulator signature
        simulator_signature = calculate_notification_signature(
            body, signature_key
        )

        # MUST match byte-for-byte
        assert simulator_signature == real_signature
    finally:
        sys.path.pop(0)


def test_calculate_request_signature():
    """Test request signature calculation matches PayNow algorithm.

    Algorithm (from getpaid-paynow/client.py:67):
    - Build JSON payload with sorted headers, sorted parameters, body
    - HMAC-SHA256(payload_json.encode(), signature_key.encode())
    - base64 encode result
    """
    from getpaid_paynow.simulator.signing import calculate_request_signature

    api_key = "api-key-abc"
    idempotency_key = "idempotency-xyz"
    body = '{"amount":1000}'
    signature_key = "sig-key-123"

    # Expected payload structure
    payload = {
        "headers": {
            "Api-Key": api_key,
            "Idempotency-Key": idempotency_key,
        },
        "parameters": {},
        "body": body,
    }
    payload_json = json.dumps(payload, separators=(",", ":"))

    expected = base64.b64encode(
        hmac.new(
            signature_key.encode("utf-8"),
            payload_json.encode("utf-8"),
            hashlib.sha256,
        ).digest()
    ).decode("utf-8")

    result = calculate_request_signature(
        api_key=api_key,
        idempotency_key=idempotency_key,
        body=body,
        signature_key=signature_key,
    )

    assert result == expected
    assert isinstance(result, str)


def test_calculate_request_signature_with_parameters():
    """Test request signature with query parameters (sorted).

    Parameters must be sorted alphabetically by key.
    """
    from getpaid_paynow.simulator.signing import calculate_request_signature

    api_key = "api-key-abc"
    idempotency_key = "idempotency-xyz"
    body = '{"amount":2000}'
    signature_key = "sig-key-456"
    parameters = {"z_param": "last", "a_param": "first", "m_param": "middle"}

    # Expected: parameters sorted alphabetically
    payload = {
        "headers": {
            "Api-Key": api_key,
            "Idempotency-Key": idempotency_key,
        },
        "parameters": {
            "a_param": "first",
            "m_param": "middle",
            "z_param": "last",
        },
        "body": body,
    }
    payload_json = json.dumps(payload, separators=(",", ":"))

    expected = base64.b64encode(
        hmac.new(
            signature_key.encode("utf-8"),
            payload_json.encode("utf-8"),
            hashlib.sha256,
        ).digest()
    ).decode("utf-8")

    result = calculate_request_signature(
        api_key=api_key,
        idempotency_key=idempotency_key,
        body=body,
        signature_key=signature_key,
        parameters=parameters,
    )

    assert result == expected


def test_paynow_sign_webhook_returns_correct_header():
    """Test paynow_sign_webhook returns dict with Signature header.

    This is the signer callable for WebhookDelivery.
    Must return: {"Signature": "base64_signature"}
    """
    from getpaid_paynow.simulator.signing import sign_webhook

    body = b'{"orderId":"TEST123","status":"CONFIRMED"}'
    signature_key = "webhook-key-789"

    result = sign_webhook(body, signature_key)

    # Must be dict with Signature key
    assert isinstance(result, dict)
    assert "Signature" in result
    assert isinstance(result["Signature"], str)

    # Verify signature value is correct
    expected_signature = base64.b64encode(
        hmac.new(
            signature_key.encode("utf-8"),
            body.decode("utf-8").encode("utf-8"),
            hashlib.sha256,
        ).digest()
    ).decode("utf-8")

    assert result["Signature"] == expected_signature


def test_paynow_sign_webhook_accepts_bytes():
    """paynow_sign_webhook accepts a bytes body (delivery contract)."""
    from getpaid_paynow.simulator.signing import sign_webhook

    body = b'{"test":"data"}'
    signature_key = "key-123"

    result = sign_webhook(body, signature_key)

    assert isinstance(result, dict)
    assert "Signature" in result


def test_paynow_sign_webhook_empty_body():
    """Test paynow_sign_webhook handles empty body."""
    from getpaid_paynow.simulator.signing import sign_webhook

    body = b""
    signature_key = "key-456"

    result = sign_webhook(body, signature_key)

    expected_signature = base64.b64encode(
        hmac.new(
            signature_key.encode("utf-8"),
            b"",
            hashlib.sha256,
        ).digest()
    ).decode("utf-8")

    assert result["Signature"] == expected_signature
