import pytest
from getpaid_paynow.simulator.transitions import PAYNOW_TRANSITIONS
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
    test_client.app.state.state_machine.register_provider(
        "paynow", PAYNOW_TRANSITIONS
    )
    return storage


@pytest.mark.asyncio
async def test_payu_authorize_get(test_client, simulator_storage):
    order_id = simulator_storage.create_order(
        {
            "provider": "payu",
            "totalAmount": "1000",
            "currencyCode": "PLN",
            "description": "Test order",
            "continueUrl": "https://example.com/continue",
            "notifyUrl": "https://example.com/notify",
        }
    )

    response = await test_client.get(f"/sim/payu/authorize/{order_id}")
    assert response.status_code == 200
    assert "SIMULATOR" in response.text
    assert "PayU" in response.text
    assert "Approve" in response.text
    assert "Reject" in response.text


@pytest.mark.asyncio
async def test_payu_authorize_get_uses_provider_amount_minor_unit_places(
    test_client,
    simulator_storage,
):
    test_client.app.state.provider_configs["payu"][
        "amount_minor_unit_places"
    ] = 0
    order_id = simulator_storage.create_order(
        {
            "provider": "payu",
            "totalAmount": "1000",
            "currencyCode": "PLN",
            "description": "Test order",
            "continueUrl": "https://example.com/continue",
            "notifyUrl": "https://example.com/notify",
        }
    )

    response = await test_client.get(f"/sim/payu/authorize/{order_id}")

    assert response.status_code == 200
    assert "1000.00 PLN" in response.text
    assert "10.00 PLN" not in response.text


@pytest.mark.asyncio
async def test_payu_authorize_get_404(test_client):
    response = await test_client.get("/sim/payu/authorize/non-existent-order")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_payu_authorize_post_approve(test_client, simulator_storage):
    order_id = simulator_storage.create_order(
        {
            "provider": "payu",
            "totalAmount": "1000",
            "currencyCode": "PLN",
            "continueUrl": "https://example.com/continue",
        }
    )
    test_client.app.state.state_machine.transition(order_id, "PENDING")

    response = await test_client.post(
        f"/sim/payu/authorize/{order_id}",
        data={"action": "approve"},
        follow_redirects=False,
    )

    assert response.status_code in (302, 303)
    assert response.headers["location"] == "https://example.com/continue"

    order = simulator_storage.get_order(order_id)
    assert order is not None
    assert order["status"] == "COMPLETED"


@pytest.mark.asyncio
async def test_payu_authorize_post_reject(test_client, simulator_storage):
    order_id = simulator_storage.create_order(
        {
            "provider": "payu",
            "totalAmount": "1000",
            "currencyCode": "PLN",
            "continueUrl": "https://example.com/continue",
        }
    )
    test_client.app.state.state_machine.transition(order_id, "PENDING")

    response = await test_client.post(
        f"/sim/payu/authorize/{order_id}",
        data={"action": "reject"},
        follow_redirects=False,
    )

    assert response.status_code in (302, 303)
    assert response.headers["location"] == "https://example.com/continue"

    order = simulator_storage.get_order(order_id)
    assert order is not None
    assert order["status"] == "CANCELED"


@pytest.mark.asyncio
async def test_paynow_authorize_get(test_client, simulator_storage):
    payment_id = simulator_storage.create_order(
        {
            "provider": "paynow",
            "amount": 1000,
            "currency": "PLN",
            "description": "Test PayNow",
            "continueUrl": "https://example.com/paynow-continue",
        }
    )

    response = await test_client.get(f"/sim/paynow/authorize/{payment_id}")
    assert response.status_code == 200
    assert "SIMULATOR" in response.text
    assert "PayNow" in response.text


@pytest.mark.asyncio
async def test_paynow_authorize_get_uses_provider_amount_minor_unit_places(
    test_client,
    simulator_storage,
):
    test_client.app.state.provider_configs["paynow"][
        "amount_minor_unit_places"
    ] = 0
    payment_id = simulator_storage.create_order(
        {
            "provider": "paynow",
            "amount": 1000,
            "currency": "PLN",
            "description": "Test PayNow",
            "continueUrl": "https://example.com/paynow-continue",
        }
    )

    response = await test_client.get(f"/sim/paynow/authorize/{payment_id}")

    assert response.status_code == 200
    assert "1000.00 PLN" in response.text
    assert "10.00 PLN" not in response.text


@pytest.mark.asyncio
async def test_paynow_authorize_post_approve(test_client, simulator_storage):
    payment_id = simulator_storage.create_order(
        {
            "provider": "paynow",
            "amount": 1000,
            "currency": "PLN",
            "continueUrl": "https://example.com/paynow-continue",
        }
    )

    response = await test_client.post(
        f"/sim/paynow/authorize/{payment_id}",
        data={"action": "approve"},
        follow_redirects=False,
    )

    assert response.status_code in (302, 303)
    assert response.headers["location"] == "https://example.com/paynow-continue"

    payment = simulator_storage.get_order(payment_id)
    assert payment is not None
    assert payment["status"] == "CONFIRMED"


@pytest.mark.asyncio
async def test_paynow_authorize_post_reject(test_client, simulator_storage):
    payment_id = simulator_storage.create_order(
        {
            "provider": "paynow",
            "amount": 1000,
            "currency": "PLN",
            "continueUrl": "https://example.com/paynow-continue",
        }
    )

    response = await test_client.post(
        f"/sim/paynow/authorize/{payment_id}",
        data={"action": "reject"},
        follow_redirects=False,
    )

    assert response.status_code in (302, 303)
    assert response.headers["location"] == "https://example.com/paynow-continue"

    payment = simulator_storage.get_order(payment_id)
    assert payment is not None
    assert payment["status"] == "REJECTED"


@pytest.mark.asyncio
async def test_authorize_already_processed(test_client, simulator_storage):
    order_id = simulator_storage.create_order(
        {
            "provider": "payu",
            "totalAmount": "1000",
            "currencyCode": "PLN",
            "continueUrl": "https://example.com/continue",
        }
    )

    test_client.app.state.state_machine.transition(order_id, "PENDING")
    test_client.app.state.state_machine.transition(
        order_id, "WAITING_FOR_CONFIRMATION"
    )
    test_client.app.state.state_machine.transition(order_id, "COMPLETED")

    response = await test_client.get(f"/sim/payu/authorize/{order_id}")
    assert response.status_code == 400
    assert "already processed" in response.text.lower()
