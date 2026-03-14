"""PayNow signature signing module.

Implements the exact signature algorithm used by PayNow for notification verification.
Reference: getpaid-paynow/src/getpaid_paynow/client.py

Two signature types:
1. Notification signature: HMAC-SHA256(body, signature_key) -> base64
2. Request signature: HMAC-SHA256(json_payload, signature_key) -> base64
   where json_payload = {"headers": {...}, "parameters": {...}, "body": "..."}
"""

import base64
import hashlib
import hmac
import json


def calculate_notification_signature(body: str, signature_key: str) -> str:
    """Calculate HMAC-SHA256 signature for PayNow notifications.

    Algorithm matches getpaid-paynow/client.py:_calculate_notification_signature()
    - HMAC-SHA256 of raw body string with signature key
    - base64 encode the result

    Args:
        body: Raw notification body string (JSON)
        signature_key: PayNow signature_key from config

    Returns:
        Base64-encoded HMAC-SHA256 signature string
    """
    digest = hmac.new(
        signature_key.encode("utf-8"),
        body.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return base64.b64encode(digest).decode("utf-8")


def calculate_request_signature(
    api_key: str,
    idempotency_key: str,
    body: str,
    signature_key: str,
    parameters: dict[str, str] | None = None,
) -> str:
    """Calculate HMAC-SHA256 signature for PayNow API requests.

    Algorithm matches getpaid-paynow/client.py:_calculate_request_signature()
    - Build JSON payload with sorted headers, sorted parameters, body
    - HMAC-SHA256 of payload JSON with signature key
    - base64 encode the result

    Args:
        api_key: Api-Key header value
        idempotency_key: Idempotency-Key header value
        body: JSON string of request body (or empty string)
        signature_key: PayNow signature_key from config
        parameters: Query parameters dict (optional, defaults to empty)

    Returns:
        Base64-encoded HMAC-SHA256 signature string
    """
    if parameters is None:
        parameters = {}

    headers_dict = {
        "Api-Key": api_key,
        "Idempotency-Key": idempotency_key,
    }
    sorted_headers = dict(sorted(headers_dict.items()))
    sorted_params = dict(sorted(parameters.items()))

    payload = {
        "headers": sorted_headers,
        "parameters": sorted_params,
        "body": body,
    }
    payload_json = json.dumps(payload, separators=(",", ":"))

    digest = hmac.new(
        signature_key.encode("utf-8"),
        payload_json.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return base64.b64encode(digest).decode("utf-8")


def paynow_sign_webhook(body: bytes, signature_key: str) -> dict[str, str]:
    """Sign PayNow webhook notification body.

    This is the signer callable for WebhookDelivery.
    Accepts bytes body (HTTP body), returns dict with Signature header.

    Args:
        body: Raw HTTP body bytes
        signature_key: PayNow signature_key from config

    Returns:
        Dict with Signature header: {"Signature": "base64_signature"}
    """
    # Convert bytes to string for signature calculation
    body_str = body.decode("utf-8")
    signature = calculate_notification_signature(body_str, signature_key)

    return {"Signature": signature}
