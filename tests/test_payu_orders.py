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
async def test_create_order_returns_302_with_redirect_and_stores_order(
    test_client,
):
    token = test_client.app.state.storage.create_token("145227")["access_token"]
    response = await test_client.post(
        "/payu/api/v2_1/orders",
        headers={
            "Authorization": f"Bearer {token}",
            "Host": "simulator.local",
        },
        json=_sample_order_payload(),
        follow_redirects=False,
    )

    assert response.status_code == 302
    body = response.json()
    order_id = body["orderId"]
    expected_redirect_uri = f"http://simulator.local/sim/authorize/{order_id}"

    assert body["status"]["statusCode"] == "SUCCESS"
    assert body["extOrderId"] == "ORDER-42"
    assert body["redirectUri"] == expected_redirect_uri
    assert response.headers["location"] == expected_redirect_uri

    stored_order = test_client.app.state.storage.get_order(order_id)
    assert stored_order is not None
    assert stored_order["status"] == "PENDING"
    assert stored_order["notifyUrl"] == "https://merchant.example/callback"
    assert stored_order["continueUrl"] == "https://merchant.example/continue"


@pytest.mark.asyncio
async def test_create_order_without_bearer_token_returns_401(test_client):
    response = await test_client.post(
        "/payu/api/v2_1/orders", json=_sample_order_payload()
    )

    assert response.status_code == 401
    assert response.json() == {
        "status": {
            "statusCode": "UNAUTHORIZED",
            "statusDesc": "Invalid or expired token",
        }
    }
