import pytest


def _sample_payment_payload() -> dict[str, object]:
    return {
        "amount": 1500,
        "currency": "PLN",
        "externalId": "PAYNOW-ORDER-42",
        "description": "PayNow test payment",
        "buyer": {"email": "buyer@example.com"},
    }


@pytest.mark.asyncio
async def test_paynow_create_payment(test_client, caplog):
    response = await test_client.post(
        "/v3/payments",
        headers={
            "Api-Key": "any-api-key-is-accepted",
            "Host": "simulator.local",
        },
        json=_sample_payment_payload(),
    )

    assert response.status_code == 201
    body = response.json()
    payment_id = body["paymentId"]

    assert body["status"] == "NEW"
    assert body["redirectUrl"] == (
        f"http://simulator.local/sim/paynow/authorize/{payment_id}"
    )

    stored_payment = test_client.app.state.storage.get_order(payment_id)
    assert stored_payment is not None
    assert stored_payment["provider"] == "paynow"
    assert stored_payment["status"] == "NEW"
    assert "Signature header missing" in caplog.text


@pytest.mark.asyncio
async def test_paynow_create_payment_redirect_url(test_client):
    response = await test_client.post(
        "/v3/payments",
        headers={
            "Api-Key": "different-key",
            "Host": "example.test",
            "Signature": "not-validated",
        },
        json=_sample_payment_payload(),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["redirectUrl"] == (
        f"http://example.test/sim/paynow/authorize/{body['paymentId']}"
    )


@pytest.mark.asyncio
async def test_paynow_get_status(test_client):
    create_response = await test_client.post(
        "/v3/payments",
        headers={"Api-Key": "test-key", "Signature": "abc"},
        json=_sample_payment_payload(),
    )
    payment_id = create_response.json()["paymentId"]

    status_response = await test_client.get(
        f"/v3/payments/{payment_id}/status",
        headers={"Api-Key": "another-key", "Signature": "abc"},
    )

    assert status_response.status_code == 200
    assert status_response.json() == {
        "paymentId": payment_id,
        "status": "NEW",
    }


@pytest.mark.asyncio
async def test_paynow_payment_methods(test_client):
    response = await test_client.get(
        "/v3/payments/paymentmethods",
        headers={"Api-Key": "test-key", "Signature": "abc"},
    )

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert {group["type"] for group in body} == {"PBL", "CARD", "BLIK"}

    pbl_group = next(group for group in body if group["type"] == "PBL")
    first_method = pbl_group["paymentMethods"][0]
    assert first_method == {
        "id": 2001,
        "name": "mTransfer",
        "description": "mBank",
        "image": "https://static.paynow.pl/payment-method-icons/2001.png",
        "status": "ENABLED",
        "authorizationType": "REDIRECT",
    }


@pytest.mark.asyncio
async def test_paynow_create_payment_validation(test_client):
    response = await test_client.post(
        "/v3/payments",
        headers={"Api-Key": "test-key", "Signature": "abc"},
        json={},
    )

    assert response.status_code == 400
    body = response.json()
    assert body["statusCode"] == 400
    assert body["errors"][0]["errorType"] == "VALIDATION_ERROR"
    assert "required" in body["errors"][0]["message"]


@pytest.mark.asyncio
async def test_paynow_amounts_not_centified(test_client):
    response = await test_client.post(
        "/v3/payments",
        headers={"Api-Key": "test-key", "Signature": "abc"},
        json=_sample_payment_payload(),
    )

    payment_id = response.json()["paymentId"]
    stored_payment = test_client.app.state.storage.get_order(payment_id)

    assert stored_payment is not None
    assert stored_payment["amount"] == "1500"
    assert stored_payment["amount"] != "150000"
