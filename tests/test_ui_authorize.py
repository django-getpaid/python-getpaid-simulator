import pytest

from getpaid_simulator.app import app
from getpaid_simulator.core.state import PaymentStateMachine
from getpaid_simulator.core.storage import SimulatorStorage


@pytest.fixture
def simulator_storage() -> SimulatorStorage:
    storage = SimulatorStorage()
    app.state.storage = storage
    app.state.state_machine = PaymentStateMachine(storage)
    return storage


@pytest.mark.asyncio
async def test_payu_authorize_get(
    test_client, simulator_storage: SimulatorStorage
):
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
async def test_payu_authorize_get_404(test_client):
    response = await test_client.get("/sim/payu/authorize/non-existent-order")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_payu_authorize_post_approve(
    test_client, simulator_storage: SimulatorStorage, monkeypatch
):
    order_id = simulator_storage.create_order(
        {
            "provider": "payu",
            "totalAmount": "1000",
            "currencyCode": "PLN",
            "continueUrl": "https://example.com/continue",
        }
    )
    app.state.state_machine.transition(order_id, "PENDING")

    webhook_triggered = False

    async def fake_trigger_webhook(*args, **kwargs):
        nonlocal webhook_triggered
        webhook_triggered = True

    import getpaid_simulator.ui.routes

    monkeypatch.setattr(
        getpaid_simulator.ui.routes,
        "trigger_payu_webhook",
        fake_trigger_webhook,
    )

    response = await test_client.post(
        f"/sim/payu/authorize/{order_id}",
        data={"action": "approve"},
        follow_redirects=False,
    )

    assert response.status_code in (302, 303)
    assert response.headers["location"] == "https://example.com/continue"
    assert webhook_triggered

    order = simulator_storage.get_order(order_id)
    assert order is not None
    assert order["status"] == "COMPLETED"


@pytest.mark.asyncio
async def test_payu_authorize_post_reject(
    test_client, simulator_storage: SimulatorStorage, monkeypatch
):
    order_id = simulator_storage.create_order(
        {
            "provider": "payu",
            "totalAmount": "1000",
            "currencyCode": "PLN",
            "continueUrl": "https://example.com/continue",
        }
    )
    app.state.state_machine.transition(order_id, "PENDING")

    webhook_triggered = False

    async def fake_trigger_webhook(*args, **kwargs):
        nonlocal webhook_triggered
        webhook_triggered = True

    import getpaid_simulator.ui.routes

    monkeypatch.setattr(
        getpaid_simulator.ui.routes,
        "trigger_payu_webhook",
        fake_trigger_webhook,
    )

    response = await test_client.post(
        f"/sim/payu/authorize/{order_id}",
        data={"action": "reject"},
        follow_redirects=False,
    )

    assert response.status_code in (302, 303)
    assert response.headers["location"] == "https://example.com/continue"
    assert webhook_triggered

    order = simulator_storage.get_order(order_id)
    assert order is not None
    assert order["status"] == "CANCELED"


@pytest.mark.asyncio
async def test_paynow_authorize_get(
    test_client, simulator_storage: SimulatorStorage
):
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
async def test_paynow_authorize_post_approve(
    test_client, simulator_storage: SimulatorStorage
):
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
async def test_paynow_authorize_post_reject(
    test_client, simulator_storage: SimulatorStorage
):
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
async def test_authorize_already_processed(
    test_client, simulator_storage: SimulatorStorage
):
    order_id = simulator_storage.create_order(
        {
            "provider": "payu",
            "totalAmount": "1000",
            "currencyCode": "PLN",
            "continueUrl": "https://example.com/continue",
        }
    )

    app.state.state_machine.transition(order_id, "PENDING")
    app.state.state_machine.transition(order_id, "WAITING_FOR_CONFIRMATION")
    app.state.state_machine.transition(order_id, "COMPLETED")

    response = await test_client.get(f"/sim/payu/authorize/{order_id}")
    assert response.status_code == 400
    assert "already processed" in response.text.lower()
