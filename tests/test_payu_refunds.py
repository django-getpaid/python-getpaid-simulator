"""Tests for PayU refund endpoint."""

from __future__ import annotations

import pytest


def _sample_order_payload() -> dict[str, object]:
    return {
        "notifyUrl": "https://merchant.example/callback",
        "customerIp": "127.0.0.1",
        "merchantPosId": "145227",
        "description": "RTV market",
        "currencyCode": "PLN",
        "totalAmount": "21000",
        "extOrderId": "ORDER-42",
        "continueUrl": "https://merchant.example/continue",
        "buyer": {
            "email": "john.doe@example.com",
            "phone": "654111654",
            "firstName": "John",
            "lastName": "Doe",
            "language": "pl",
        },
        "products": [
            {
                "name": "Wireless Mouse",
                "unitPrice": "21000",
                "quantity": "1",
            }
        ],
    }


@pytest.mark.asyncio
async def test_payu_refund_endpoint_returns_correct_format(test_client):
    """POST /orders/{order_id}/refunds returns the PayU format."""
    # Create and authorize order first
    token = test_client.app.state.storage.create_token("145227")["access_token"]
    response = await test_client.post(
        "/payu/api/v2_1/orders",
        headers={"Authorization": f"Bearer {token}", "Host": "simulator.local"},
        json=_sample_order_payload(),
        follow_redirects=False,
    )
    order_id = response.json()["orderId"]

    # Request refund
    refund_payload = {
        "refund": {
            "description": "Customer requested refund",
            "amount": "10000",
            "currencyCode": "PLN",
        }
    }
    refund_response = await test_client.post(
        f"/payu/api/v2_1/orders/{order_id}/refunds",
        headers={"Authorization": f"Bearer {token}"},
        json=refund_payload,
    )

    assert refund_response.status_code == 200
    body = refund_response.json()

    # Verify PayU response structure
    assert "status" in body
    assert body["status"]["statusCode"] == "SUCCESS"

    assert "refund" in body
    refund = body["refund"]
    assert "refundId" in refund
    assert "amount" in refund
    assert refund["amount"] == "10000"
    assert refund["currencyCode"] == "PLN"
    assert refund["status"] == "FINALIZED"
    assert "statusDateTime" in refund

    # Verify refund stored
    refunds = test_client.app.state.storage.get_refunds(order_id)
    assert len(refunds) == 1
    assert refunds[0]["amount"] == "10000"


@pytest.mark.asyncio
async def test_payu_refund_endpoint_uses_ext_refund_id_if_provided(
    test_client,
):
    """Test refund endpoint preserves extRefundId from request."""
    token = test_client.app.state.storage.create_token("145227")["access_token"]
    response = await test_client.post(
        "/payu/api/v2_1/orders",
        headers={"Authorization": f"Bearer {token}", "Host": "simulator.local"},
        json=_sample_order_payload(),
        follow_redirects=False,
    )
    order_id = response.json()["orderId"]

    refund_payload = {
        "refund": {
            "description": "Refund with external ID",
            "amount": "5000",
            "extRefundId": "EXT-REFUND-123",
            "currencyCode": "PLN",
        }
    }
    refund_response = await test_client.post(
        f"/payu/api/v2_1/orders/{order_id}/refunds",
        headers={"Authorization": f"Bearer {token}"},
        json=refund_payload,
    )

    assert refund_response.status_code == 200
    body = refund_response.json()
    assert body["refund"]["extRefundId"] == "EXT-REFUND-123"


@pytest.mark.asyncio
async def test_payu_refund_nonexistent_order_returns_404(test_client):
    """Test refund request for nonexistent order returns 404."""
    token = test_client.app.state.storage.create_token("145227")["access_token"]
    refund_payload = {
        "refund": {
            "description": "Refund for missing order",
            "amount": "1000",
            "currencyCode": "PLN",
        }
    }

    response = await test_client.post(
        "/payu/api/v2_1/orders/missing-order-id/refunds",
        headers={"Authorization": f"Bearer {token}"},
        json=refund_payload,
    )

    assert response.status_code == 404
    assert response.json()["status"]["statusCode"] == "ERROR_ORDER_NOT_EXISTS"


@pytest.mark.asyncio
async def test_payu_refund_without_authorization_returns_401(test_client):
    """Test refund endpoint requires valid bearer token."""
    refund_payload = {
        "refund": {
            "description": "Unauthorized refund",
            "amount": "1000",
            "currencyCode": "PLN",
        }
    }

    response = await test_client.post(
        "/payu/api/v2_1/orders/some-order-id/refunds",
        json=refund_payload,
    )

    assert response.status_code == 401
    assert response.json()["status"]["statusCode"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_payu_refund_full_amount_without_explicit_amount(test_client):
    """Test refund without amount field refunds full order amount."""
    token = test_client.app.state.storage.create_token("145227")["access_token"]
    response = await test_client.post(
        "/payu/api/v2_1/orders",
        headers={"Authorization": f"Bearer {token}", "Host": "simulator.local"},
        json=_sample_order_payload(),
        follow_redirects=False,
    )
    order_id = response.json()["orderId"]

    refund_payload = {
        "refund": {
            "description": "Full refund",
            "currencyCode": "PLN",
        }
    }
    refund_response = await test_client.post(
        f"/payu/api/v2_1/orders/{order_id}/refunds",
        headers={"Authorization": f"Bearer {token}"},
        json=refund_payload,
    )

    assert refund_response.status_code == 200
    body = refund_response.json()
    # Should refund full amount from order
    assert body["refund"]["amount"] == "21000"
