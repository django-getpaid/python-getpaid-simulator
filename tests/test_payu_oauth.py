"""Tests for PayU OAuth2 endpoint and signature signing."""

import time
from datetime import UTC
from datetime import datetime
from datetime import timedelta

import pytest
from litestar.testing import AsyncTestClient

from getpaid_simulator.app import app
from getpaid_simulator.core.storage import SimulatorStorage
from getpaid_simulator.providers.payu.signing import compute_signature
from getpaid_simulator.providers.payu.signing import sign_payload


class TestOAuthEndpoint:
    """Tests for OAuth2 token endpoint."""

    async def test_oauth_endpoint_success(self, test_client: AsyncTestClient):
        """POST form-encoded credentials returns 200 + token JSON."""
        response = await test_client.post(
            "/payu/pl/standard/user/oauth/authorize",
            data={
                "grant_type": "client_credentials",
                "client_id": "300746",
                "client_secret": "2ee86a66e5d97e3fadc400c9f19b065d",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert isinstance(data["access_token"], str)
        assert len(data["access_token"]) == 32  # uuid4().hex length

    async def test_oauth_token_format_validation(
        self, test_client: AsyncTestClient
    ):
        """Response has correct PayU OAuth format."""
        response = await test_client.post(
            "/payu/pl/standard/user/oauth/authorize",
            data={
                "grant_type": "client_credentials",
                "client_id": "300746",
                "client_secret": "2ee86a66e5d97e3fadc400c9f19b065d",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        data = response.json()
        assert data["token_type"] == "bearer"
        assert data["expires_in"] == 43199
        assert data["grant_type"] == "client_credentials"

    async def test_oauth_accepts_any_credentials(
        self, test_client: AsyncTestClient
    ):
        """Accept ANY client_id/client_secret pair (zero friction)."""
        response = await test_client.post(
            "/payu/pl/standard/user/oauth/authorize",
            data={
                "grant_type": "client_credentials",
                "client_id": "fake_id",
                "client_secret": "fake_secret",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data

    async def test_oauth_token_stored_in_storage(
        self, test_client: AsyncTestClient
    ):
        """Token is stored in SimulatorStorage after creation."""
        response = await test_client.post(
            "/payu/pl/standard/user/oauth/authorize",
            data={
                "grant_type": "client_credentials",
                "client_id": "300746",
                "client_secret": "2ee86a66e5d97e3fadc400c9f19b065d",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        token = response.json()["access_token"]

        # Access storage from app state
        storage = app.state.storage
        assert storage.validate_token(token) is True

    async def test_oauth_token_expiry_stored(
        self, test_client: AsyncTestClient
    ):
        """Token has correct expiry time (43199 seconds)."""
        response = await test_client.post(
            "/payu/pl/standard/user/oauth/authorize",
            data={
                "grant_type": "client_credentials",
                "client_id": "300746",
                "client_secret": "2ee86a66e5d97e3fadc400c9f19b065d",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        token = response.json()["access_token"]

        # Check token is valid now
        storage = app.state.storage
        assert storage.validate_token(token) is True

        # Manually expire the token by manipulating storage
        token_data = storage._tokens[token]
        token_data["expires_at"] = datetime.now(UTC) - timedelta(seconds=1)

        # Check token is now invalid
        assert storage.validate_token(token) is False


class TestBearerTokenMiddleware:
    """Tests for Bearer token validation middleware."""

    async def test_middleware_success_with_valid_token(
        self, test_client: AsyncTestClient
    ):
        """Valid Bearer token allows request through."""
        # First, get a token
        oauth_response = await test_client.post(
            "/payu/pl/standard/user/oauth/authorize",
            data={
                "grant_type": "client_credentials",
                "client_id": "300746",
                "client_secret": "2ee86a66e5d97e3fadc400c9f19b065d",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        token = oauth_response.json()["access_token"]

        # Then, use it on a protected endpoint (we'll create a test endpoint)
        # For now, we test that middleware extracts and validates the token
        # The actual endpoint implementation is Task 7/8
        # We'll test with a placeholder endpoint that returns 200 if auth passes
        response = await test_client.get(
            "/payu/api/v2_1/test-protected",
            headers={"Authorization": f"Bearer {token}"},
        )
        # If middleware is working, request should proceed (not 401)
        # If endpoint doesn't exist yet, might be 404, but not 401
        assert response.status_code != 401

    async def test_middleware_401_missing_token(
        self, test_client: AsyncTestClient
    ):
        """Missing Authorization header returns 401."""
        response = await test_client.get("/payu/api/v2_1/test-protected")
        assert response.status_code == 401
        data = response.json()
        assert data["status"]["statusCode"] == "UNAUTHORIZED"
        assert "Invalid or expired token" in data["status"]["statusDesc"]

    async def test_middleware_401_invalid_token(
        self, test_client: AsyncTestClient
    ):
        """Invalid token returns 401 with PayU error format."""
        response = await test_client.get(
            "/payu/api/v2_1/test-protected",
            headers={"Authorization": "Bearer invalid_token_12345"},
        )
        assert response.status_code == 401
        data = response.json()
        assert data["status"]["statusCode"] == "UNAUTHORIZED"
        assert "Invalid or expired token" in data["status"]["statusDesc"]

    async def test_middleware_401_expired_token(
        self, test_client: AsyncTestClient
    ):
        """Expired token returns 401 with PayU error format."""
        # Get a token
        oauth_response = await test_client.post(
            "/payu/pl/standard/user/oauth/authorize",
            data={
                "grant_type": "client_credentials",
                "client_id": "300746",
                "client_secret": "2ee86a66e5d97e3fadc400c9f19b065d",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        token = oauth_response.json()["access_token"]

        # Manually expire it
        storage = app.state.storage
        token_data = storage._tokens[token]
        token_data["expires_at"] = datetime.now(UTC) - timedelta(seconds=1)

        # Use expired token
        response = await test_client.get(
            "/payu/api/v2_1/test-protected",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 401
        data = response.json()
        assert data["status"]["statusCode"] == "UNAUTHORIZED"

    async def test_middleware_401_malformed_header(
        self, test_client: AsyncTestClient
    ):
        """Malformed Authorization header returns 401."""
        response = await test_client.get(
            "/payu/api/v2_1/test-protected",
            headers={"Authorization": "InvalidFormat"},
        )
        assert response.status_code == 401


class TestSignatureModule:
    """Tests for signature computation and formatting."""

    def test_compute_signature_known_input(self):
        """Signature computation produces correct hex for known input."""
        # Test with known values from PayU processor verification logic
        body = b'{"orderId":"TEST123","status":"COMPLETED"}'
        second_key = "b6ca15b0d1020e8094d9b5f8d163db54"

        signature = compute_signature(body, second_key)

        # Verify it's a hex string
        assert isinstance(signature, str)
        assert len(signature) == 64  # SHA-256 produces 64 hex chars
        assert all(c in "0123456789abcdef" for c in signature)

        # Verify algorithm matches processor.py:184
        # expected = algorithm(f"{raw_body}{second_key}".encode()).hexdigest()
        from hashlib import sha256

        expected = sha256(body + second_key.encode()).hexdigest()
        assert signature == expected

    def test_compute_signature_empty_body(self):
        """Signature works with empty body."""
        body = b""
        second_key = "test_key"

        signature = compute_signature(body, second_key)

        from hashlib import sha256

        expected = sha256(second_key.encode()).hexdigest()
        assert signature == expected

    def test_sign_payload_format(self):
        """sign_payload returns correct header format."""
        body = b'{"test":"data"}'
        second_key = "b6ca15b0d1020e8094d9b5f8d163db54"

        result = sign_payload(body, second_key)

        # Should match format: signature=<hex>;algorithm=SHA-256;sender=checkout
        assert result.startswith("signature=")
        assert ";algorithm=SHA-256;" in result
        assert result.endswith(";sender=checkout")

        # Extract signature part and verify it's correct
        parts = dict(item.split("=", 1) for item in result.split(";"))
        assert "signature" in parts
        assert "algorithm" in parts
        assert "sender" in parts
        assert parts["algorithm"] == "SHA-256"
        assert parts["sender"] == "checkout"

        # Verify signature matches compute_signature
        expected_sig = compute_signature(body, second_key)
        assert parts["signature"] == expected_sig

    def test_sign_payload_integration_with_processor(self):
        """Signature passes PayU processor's verify_callback() verification."""
        # This test simulates what the processor does in processor.py:124-196
        body = (
            b'{"orderId":"ORDER123","extOrderId":"ext-1","status":"COMPLETED"}'
        )
        second_key = "b6ca15b0d1020e8094d9b5f8d163db54"

        # Generate signature using our signing module
        header_value = sign_payload(body, second_key)

        # Simulate processor verification logic
        parsed = dict(
            item.split("=", 1)
            for item in header_value.split(";")
            if "=" in item
        )
        signature = parsed.get("signature", "")
        algo_name = parsed.get("algorithm", "SHA-256").upper()

        from hashlib import sha256
        import hmac

        algorithm = sha256
        expected = algorithm(body + second_key.encode()).hexdigest()

        # This is the exact check from processor.py:186
        assert hmac.compare_digest(expected, signature)
