"""Tests for PayNow refund endpoints (TDD)."""

from __future__ import annotations

import pytest


def _sample_payment_payload() -> dict[str, object]:
    return {
        "amount": 2000,
        "currency": "PLN",
        "externalId": "PAYNOW-REFUND-TEST",
        "description": "PayNow refund test payment",
        "buyer": {"email": "refund@example.com"},
    }


@pytest.mark.asyncio
async def test_paynow_create_refund(test_client):
    """Test POST /v3/payments/{payment_id}/refunds creates refund and returns 201."""
    # Create payment first
    create_response = await test_client.post(
        "/paynow/v3/payments",
        headers={"Api-Key": "test-key", "Signature": "abc"},
        json=_sample_payment_payload(),
    )
    payment_id = create_response.json()["paymentId"]

    # Transition to CONFIRMED (refunds only allowed on confirmed payments)
    # PayNow requires: NEW → PENDING → CONFIRMED
    test_client.app.state.state_machine.transition(payment_id, "PENDING")
    test_client.app.state.state_machine.transition(payment_id, "CONFIRMED")

    # Create refund
    refund_response = await test_client.post(
        f"/paynow/v3/payments/{payment_id}/refunds",
        headers={"Api-Key": "test-key", "Signature": "abc"},
        json={"amount": 500, "reason": "RMA"},
    )

    assert refund_response.status_code == 201
    body = refund_response.json()
    assert "refundId" in body
    assert body["status"] == "SUCCESSFUL"

    # Verify refund stored
    refunds = test_client.app.state.storage.get_refunds(payment_id)
    assert len(refunds) == 1
    assert refunds[0]["amount"] == "500"
    assert refunds[0]["status"] == "SUCCESSFUL"


@pytest.mark.asyncio
async def test_paynow_create_refund_not_confirmed(test_client):
    """Test refund endpoint returns error if payment not in CONFIRMED status."""
    # Create payment (status=NEW)
    create_response = await test_client.post(
        "/paynow/v3/payments",
        headers={"Api-Key": "test-key", "Signature": "abc"},
        json=_sample_payment_payload(),
    )
    payment_id = create_response.json()["paymentId"]

    # Attempt refund on NEW payment
    refund_response = await test_client.post(
        f"/paynow/v3/payments/{payment_id}/refunds",
        headers={"Api-Key": "test-key", "Signature": "abc"},
        json={"amount": 500, "reason": "RMA"},
    )

    assert refund_response.status_code == 400
    body = refund_response.json()
    assert body["statusCode"] == 400
    assert body["errors"][0]["errorType"] == "VALIDATION_ERROR"
    assert "CONFIRMED" in body["errors"][0]["message"]


@pytest.mark.asyncio
async def test_paynow_create_refund_payment_not_found(test_client):
    """Test refund endpoint returns 404 if payment doesn't exist."""
    refund_response = await test_client.post(
        "/paynow/v3/payments/nonexistent-payment/refunds",
        headers={"Api-Key": "test-key", "Signature": "abc"},
        json={"amount": 500, "reason": "RMA"},
    )

    assert refund_response.status_code == 404
    body = refund_response.json()
    assert body["statusCode"] == 404
    assert body["errors"][0]["errorType"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_paynow_get_refund_status(test_client):
    """Test GET /v3/refunds/{refund_id}/status returns refund status."""
    # Create and confirm payment
    create_response = await test_client.post(
        "/paynow/v3/payments",
        headers={"Api-Key": "test-key", "Signature": "abc"},
        json=_sample_payment_payload(),
    )
    payment_id = create_response.json()["paymentId"]
    test_client.app.state.state_machine.transition(payment_id, "PENDING")
    test_client.app.state.state_machine.transition(payment_id, "CONFIRMED")

    # Create refund
    refund_response = await test_client.post(
        f"/paynow/v3/payments/{payment_id}/refunds",
        headers={"Api-Key": "test-key", "Signature": "abc"},
        json={"amount": 750, "reason": "OTHER"},
    )
    refund_id = refund_response.json()["refundId"]

    # Get refund status
    status_response = await test_client.get(
        f"/paynow/v3/refunds/{refund_id}/status",
        headers={"Api-Key": "test-key", "Signature": "abc"},
    )

    assert status_response.status_code == 200
    body = status_response.json()
    assert body["refundId"] == refund_id
    assert body["status"] == "SUCCESSFUL"
    assert body["amount"] == 750


@pytest.mark.asyncio
async def test_paynow_get_refund_status_not_found(test_client):
    """Test GET /v3/refunds/{refund_id}/status returns 404 for nonexistent refund."""
    status_response = await test_client.get(
        "/paynow/v3/refunds/nonexistent-refund/status",
        headers={"Api-Key": "test-key", "Signature": "abc"},
    )

    assert status_response.status_code == 404
    body = status_response.json()
    assert body["statusCode"] == 404
    assert body["errors"][0]["errorType"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_paynow_cancel_refund(test_client):
    """Test POST /v3/refunds/{refund_id}/cancel cancels a refund."""
    # Create and confirm payment
    create_response = await test_client.post(
        "/paynow/v3/payments",
        headers={"Api-Key": "test-key", "Signature": "abc"},
        json=_sample_payment_payload(),
    )
    payment_id = create_response.json()["paymentId"]
    test_client.app.state.state_machine.transition(payment_id, "PENDING")
    test_client.app.state.state_machine.transition(payment_id, "CONFIRMED")

    # Create refund
    refund_response = await test_client.post(
        f"/paynow/v3/payments/{payment_id}/refunds",
        headers={"Api-Key": "test-key", "Signature": "abc"},
        json={"amount": 1000, "reason": "REFUND_BEFORE_14"},
    )
    refund_id = refund_response.json()["refundId"]

    # Note: In simulator, refunds are immediately SUCCESSFUL, so cancel won't do much
    # but we need to support the endpoint for API contract completeness
    cancel_response = await test_client.post(
        f"/paynow/v3/refunds/{refund_id}/cancel",
        headers={"Api-Key": "test-key", "Signature": "abc"},
    )

    # In real PayNow, cancel only works on PENDING/NEW refunds
    # In simulator, we'll accept it but note it's already SUCCESSFUL
    assert cancel_response.status_code == 200
    body = cancel_response.json()
    assert body["refundId"] == refund_id
    assert body["status"] == "CANCELLED"


@pytest.mark.asyncio
async def test_paynow_cancel_refund_not_found(test_client):
    """Test POST /v3/refunds/{refund_id}/cancel returns 404 for nonexistent refund."""
    cancel_response = await test_client.post(
        "/paynow/v3/refunds/nonexistent-refund/cancel",
        headers={"Api-Key": "test-key", "Signature": "abc"},
    )

    assert cancel_response.status_code == 404
    body = cancel_response.json()
    assert body["statusCode"] == 404
    assert body["errors"][0]["errorType"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_paynow_refund_error_format(test_client):
    """Test refund errors use PayNow format: {statusCode, errors: [{errorType, message}]}."""
    # Try to refund nonexistent payment
    refund_response = await test_client.post(
        "/paynow/v3/payments/fake-id/refunds",
        headers={"Api-Key": "test-key", "Signature": "abc"},
        json={"amount": 100, "reason": "RMA"},
    )

    assert refund_response.status_code == 404
    body = refund_response.json()

    # Verify PayNow error structure
    assert "statusCode" in body
    assert "errors" in body
    assert isinstance(body["errors"], list)
    assert len(body["errors"]) > 0
    assert "errorType" in body["errors"][0]
    assert "message" in body["errors"][0]
    assert body["statusCode"] == 404
    assert body["errors"][0]["errorType"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_paynow_refund_amount_not_centified(test_client):
    """Test refund amounts are stored as integers (not centified)."""
    # Create and confirm payment
    create_response = await test_client.post(
        "/paynow/v3/payments",
        headers={"Api-Key": "test-key", "Signature": "abc"},
        json=_sample_payment_payload(),
    )
    payment_id = create_response.json()["paymentId"]
    test_client.app.state.state_machine.transition(payment_id, "PENDING")
    test_client.app.state.state_machine.transition(payment_id, "CONFIRMED")

    # Create refund with amount 500 (should be stored as "500", not "50000")
    refund_response = await test_client.post(
        f"/paynow/v3/payments/{payment_id}/refunds",
        headers={"Api-Key": "test-key", "Signature": "abc"},
        json={"amount": 500, "reason": "RMA"},
    )
    refund_id = refund_response.json()["refundId"]

    # Verify amount is NOT centified
    refunds = test_client.app.state.storage.get_refunds(payment_id)
    assert len(refunds) == 1
    assert refunds[0]["amount"] == "500"
    assert refunds[0]["amount"] != "50000"

    # Also verify via status endpoint
    status_response = await test_client.get(
        f"/paynow/v3/refunds/{refund_id}/status",
        headers={"Api-Key": "test-key", "Signature": "abc"},
    )
    assert status_response.json()["amount"] == 500
    assert status_response.json()["amount"] != 50000
