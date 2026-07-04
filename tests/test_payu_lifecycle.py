import pytest
from getpaid_payu.simulator.transitions import PAYU_TRANSITIONS


@pytest.fixture
def simulator_storage(test_client):
    storage = test_client.app.state.storage
    storage._orders.clear()
    storage._tokens.clear()
    storage._refunds.clear()
    test_client.app.state.state_machine.register_provider(
        "payu", PAYU_TRANSITIONS
    )
    return storage


@pytest.fixture
def auth_headers(simulator_storage) -> dict[str, str]:
    token = simulator_storage.create_token("300746")["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_order_info_and_cancel(
    test_client, simulator_storage, auth_headers
):
    order_id = simulator_storage.create_order(
        {
            "provider": "payu",
            "extOrderId": "ext-1",
            "status": "PENDING",
            "totalAmount": "10000",
            "currencyCode": "PLN",
            "description": "Test order",
        }
    )

    info_response = await test_client.get(
        f"/payu/api/v2_1/orders/{order_id}",
        headers=auth_headers,
    )
    assert info_response.status_code == 200
    info_payload = info_response.json()
    assert info_payload["status"]["statusCode"] == "SUCCESS"
    assert info_payload["orders"][0]["orderId"] == order_id
    assert info_payload["orders"][0]["totalAmount"] == "10000"
    assert info_payload["orders"][0]["status"] == "PENDING"

    cancel_response = await test_client.delete(
        f"/payu/api/v2_1/orders/{order_id}",
        headers=auth_headers,
    )
    assert cancel_response.status_code == 200
    assert cancel_response.json() == {
        "status": {"statusCode": "SUCCESS"},
        "orderId": order_id,
    }

    canceled_info = await test_client.get(
        f"/payu/api/v2_1/orders/{order_id}",
        headers=auth_headers,
    )
    assert canceled_info.status_code == 200
    assert canceled_info.json()["orders"][0]["status"] == "CANCELED"


@pytest.mark.asyncio
async def test_cancel_completed_order_returns_error_value_invalid(
    test_client,
    simulator_storage,
    auth_headers,
):
    order_id = simulator_storage.create_order(
        {
            "provider": "payu",
            "extOrderId": "ext-completed",
            "status": "COMPLETED",
            "totalAmount": "5000",
            "currencyCode": "PLN",
            "description": "Completed order",
        }
    )

    response = await test_client.delete(
        f"/payu/api/v2_1/orders/{order_id}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"]["statusCode"] == "ERROR_VALUE_INVALID"


@pytest.mark.asyncio
async def test_capture_waiting_for_confirmation_order(
    test_client,
    simulator_storage,
    auth_headers,
):
    order_id = simulator_storage.create_order(
        {
            "provider": "payu",
            "extOrderId": "ext-capture",
            "status": "WAITING_FOR_CONFIRMATION",
            "totalAmount": "7000",
            "currencyCode": "PLN",
            "description": "Capture order",
            "notifyUrl": "https://example.com/notify",
        }
    )

    response = await test_client.post(
        f"/payu/api/v2_1/orders/{order_id}/captures",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": {"statusCode": "SUCCESS"},
        "orderId": order_id,
    }
    stored_order = simulator_storage.get_order(order_id)
    assert stored_order is not None
    assert stored_order["status"] == "COMPLETED"


@pytest.mark.asyncio
async def test_capture_pending_order_returns_error_value_invalid(
    test_client,
    simulator_storage,
    auth_headers,
):
    order_id = simulator_storage.create_order(
        {
            "provider": "payu",
            "extOrderId": "ext-pending",
            "status": "PENDING",
            "totalAmount": "6000",
            "currencyCode": "PLN",
            "description": "Pending order",
        }
    )

    response = await test_client.post(
        f"/payu/api/v2_1/orders/{order_id}/captures",
        headers=auth_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"]["statusCode"] == "ERROR_VALUE_INVALID"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/payu/api/v2_1/orders/missing-order"),
        ("delete", "/payu/api/v2_1/orders/missing-order"),
        ("post", "/payu/api/v2_1/orders/missing-order/captures"),
    ],
)
async def test_non_existent_order_returns_404(
    test_client,
    simulator_storage,
    auth_headers,
    method,
    path,
):
    response = await getattr(test_client, method)(path, headers=auth_headers)
    assert response.status_code == 404
    payload = response.json()
    assert "status" in payload
    assert "statusCode" in payload["status"]
