import pytest
from litestar import get
from litestar.testing import AsyncTestClient

import getpaid_simulator.app as app_module
from getpaid_simulator.plugins import PluginLoadResult
from getpaid_simulator.plugins import ProviderLoadFailure
from getpaid_simulator.spi import SIMULATOR_PLUGIN_API_VERSION
from getpaid_simulator.spi import SimulatorProviderPlugin


@get("/fake/provider")
async def fake_provider_route() -> dict[str, str]:
    return {"provider": "fakepay"}


def _make_plugin(
    *,
    slug: str = "fakepay",
    display_name: str = "FakePay",
) -> SimulatorProviderPlugin:
    return SimulatorProviderPlugin(
        api_version=SIMULATOR_PLUGIN_API_VERSION,
        slug=slug,
        display_name=display_name,
        api_handlers=(fake_provider_route,),
        ui_handlers=(),
        transitions={"NEW": {"PENDING"}},
        load_config=lambda env: {},
    )


def test_create_app_stores_loaded_and_failed_plugins(monkeypatch):
    monkeypatch.setattr(
        app_module,
        "load_provider_plugins",
        lambda config: PluginLoadResult(
            loaded_plugins=(_make_plugin(),),
            failed_plugins=(
                ProviderLoadFailure(
                    slug="brokenpay",
                    stage="import",
                    error="boom",
                ),
            ),
            provider_configs={"fakepay": {}},
        ),
    )

    app = app_module.create_app()

    assert list(app.state.loaded_plugins) == ["fakepay"]
    assert app.state.failed_plugins[0].slug == "brokenpay"


def test_create_app_logs_loaded_and_failed_plugins(monkeypatch, caplog):
    monkeypatch.setattr(
        app_module,
        "load_provider_plugins",
        lambda config: PluginLoadResult(
            loaded_plugins=(_make_plugin(display_name="FakePay"),),
            failed_plugins=(
                ProviderLoadFailure(
                    slug="brokenpay",
                    stage="config",
                    error="invalid config",
                ),
            ),
            provider_configs={"fakepay": {}},
        ),
    )

    with caplog.at_level("INFO"):
        app_module.create_app()

    assert "Loaded simulator plugins: FakePay" in caplog.text
    assert "Failed simulator plugins: brokenpay" in caplog.text


@pytest.mark.asyncio
async def test_create_app_mounts_routes_from_loaded_plugins(monkeypatch):
    monkeypatch.setattr(
        app_module,
        "load_provider_plugins",
        lambda config: PluginLoadResult(
            loaded_plugins=(_make_plugin(),),
            failed_plugins=(),
            provider_configs={"fakepay": {}},
        ),
    )
    app = app_module.create_app()

    async with AsyncTestClient(app=app) as test_client:
        response = await test_client.get("/fake/provider")

    assert response.status_code == 200
    assert response.json() == {"provider": "fakepay"}


@pytest.mark.asyncio
async def test_health_endpoint_reports_degraded_status_when_plugins_fail(
    monkeypatch,
):
    monkeypatch.setattr(
        app_module,
        "load_provider_plugins",
        lambda config: PluginLoadResult(
            loaded_plugins=(_make_plugin(),),
            failed_plugins=(
                ProviderLoadFailure(
                    slug="brokenpay",
                    stage="register",
                    error="bad handlers",
                ),
            ),
            provider_configs={"fakepay": {}},
        ),
    )
    app = app_module.create_app()

    async with AsyncTestClient(app=app) as test_client:
        response = await test_client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "status": "degraded",
        "service": "getpaid-simulator",
        "loadedProviders": ["fakepay"],
        "failedProviders": ["brokenpay"],
    }


@pytest.mark.asyncio
async def test_dashboard_renders_dynamic_filters_and_plugin_warning(
    monkeypatch,
):
    monkeypatch.setattr(
        app_module,
        "load_provider_plugins",
        lambda config: PluginLoadResult(
            loaded_plugins=(_make_plugin(display_name="FakePay"),),
            failed_plugins=(
                ProviderLoadFailure(
                    slug="brokenpay",
                    stage="import",
                    error="boom",
                ),
            ),
            provider_configs={"fakepay": {}},
        ),
    )
    app = app_module.create_app()

    async with AsyncTestClient(app=app) as test_client:
        response = await test_client.get("/sim/dashboard")

    assert response.status_code == 200
    body = response.text
    assert "FakePay" in body
    assert "brokenpay" in body
