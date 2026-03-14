import pytest
from litestar.testing import AsyncTestClient

import getpaid_simulator.app as app_module


def test_default_app_state_contains_discovered_providers():
    discovered = set(app_module.app.state.discovered_providers)
    assert {"payu", "paynow"}.issubset(discovered)


def test_create_app_logs_discovered_providers(monkeypatch, caplog):
    monkeypatch.setattr(
        app_module,
        "discover_providers",
        lambda: ["payu", "paynow"],
    )

    with caplog.at_level("INFO"):
        app_module.create_app()

    assert "Discovered providers: PayU, PayNow" in caplog.text


@pytest.mark.asyncio
async def test_create_app_mounts_routes_for_discovered_providers(monkeypatch):
    monkeypatch.setattr(app_module, "discover_providers", lambda: ["payu"])
    app = app_module.create_app()

    async with AsyncTestClient(app=app) as test_client:
        payu_response = await test_client.get("/payu/api/v2_1/test-protected")
        paynow_response = await test_client.get("/v3/payments/paymentmethods")

    assert payu_response.status_code == 401
    assert paynow_response.status_code == 404
    assert app.state.discovered_providers == ["payu"]


@pytest.mark.asyncio
async def test_payu_oauth_route_path_is_unchanged():
    async with AsyncTestClient(app=app_module.app) as test_client:
        response = await test_client.post(
            "/payu/pl/standard/user/oauth/authorize",
            data={
                "grant_type": "client_credentials",
                "client_id": "test-pos",
                "client_secret": "test-secret",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    assert response.status_code == 200
