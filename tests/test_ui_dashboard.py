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
async def test_dashboard_empty_state(test_client, simulator_storage):
    response = await test_client.get("/sim/dashboard")
    assert response.status_code == 200
    html = response.text
    assert "No payments yet" in html
    assert "Create a payment via your application to see it here." in html

@pytest.mark.asyncio
async def test_dashboard_lists_payments(test_client, simulator_storage):
    order1_id = simulator_storage.create_order(
        {"totalAmount": "1500", "currencyCode": "PLN", "description": "test"},
        provider="payu"
    )
    order2_id = simulator_storage.create_order(
        {"totalAmount": "2500", "currencyCode": "PLN", "description": "test2"},
        provider="paynow"
    )
    
    response = await test_client.get("/sim/dashboard")
    assert response.status_code == 200
    html = response.text
    
    assert "15.00 PLN" in html
    assert "25.00 PLN" in html
    
    # Check action links
    assert f"/sim/payu/authorize/{order1_id}" in html
    assert f"/sim/paynow/authorize/{order2_id}" in html

@pytest.mark.asyncio
async def test_dashboard_filter_by_provider(test_client, simulator_storage):
    order1_id = simulator_storage.create_order(
        {"totalAmount": "1500", "currencyCode": "PLN", "description": "test"},
        provider="payu"
    )
    order2_id = simulator_storage.create_order(
        {"totalAmount": "2500", "currencyCode": "PLN", "description": "test2"},
        provider="paynow"
    )
    
    response = await test_client.get("/sim/dashboard?provider=payu")
    assert response.status_code == 200
    html = response.text
    assert "15.00 PLN" in html
    assert "25.00 PLN" not in html
    assert f"/sim/payu/authorize/{order1_id}" in html
    assert f"/sim/paynow/authorize/{order2_id}" not in html
    
    response2 = await test_client.get("/sim/dashboard?provider=paynow")
    assert response2.status_code == 200
    html2 = response2.text
    assert "25.00 PLN" in html2
    assert "15.00 PLN" not in html2
    assert f"/sim/paynow/authorize/{order2_id}" in html2
    assert f"/sim/payu/authorize/{order1_id}" not in html2

@pytest.mark.asyncio
async def test_dashboard_redirects_from_root(test_client, simulator_storage):
    response = await test_client.get("/sim/")
    assert response.status_code in (200, 307)
