from types import SimpleNamespace

import pytest

import getpaid_simulator.plugins as plugins
from getpaid_simulator.core.config import SimulatorConfig
from getpaid_simulator.spi import SIMULATOR_PLUGIN_API_VERSION
from getpaid_simulator.spi import SimulatorProviderPlugin


def _plugin(
    slug: str,
    display_name: str | None = None,
    *,
    api_version: str = SIMULATOR_PLUGIN_API_VERSION,
) -> SimulatorProviderPlugin:
    return SimulatorProviderPlugin(
        api_version=api_version,
        slug=slug,
        display_name=display_name or slug.title(),
        api_handlers=(),
        ui_handlers=(),
        transitions={"NEW": {"PENDING"}},
        load_config=lambda env: {"provider": slug},
    )


def _entry_point(name: str, factory):
    return SimpleNamespace(name=name, load=lambda: factory)


def test_load_provider_plugins_uses_simulator_entry_points(monkeypatch):
    def fake_entry_points(*, group: str):
        assert group == "getpaid.simulator.providers"
        return [
            _entry_point("payu", lambda: _plugin("payu", "PayU")),
            _entry_point("paynow", lambda: _plugin("paynow", "PayNow")),
        ]

    monkeypatch.setattr(plugins, "entry_points", fake_entry_points)

    result = plugins.load_provider_plugins(SimulatorConfig())

    assert [plugin.slug for plugin in result.loaded_plugins] == [
        "paynow",
        "payu",
    ]
    assert result.failed_plugins == ()


def test_load_provider_plugins_warn_mode_skips_failed_plugin(monkeypatch):
    def fake_entry_points(*, group: str):
        assert group == "getpaid.simulator.providers"
        return [
            _entry_point("payu", lambda: _plugin("payu")),
            _entry_point(
                "brokenpay", lambda: (_ for _ in ()).throw(ImportError("boom"))
            ),
        ]

    monkeypatch.setattr(plugins, "entry_points", fake_entry_points)

    result = plugins.load_provider_plugins(
        SimulatorConfig(plugin_failure_mode="warn")
    )

    assert [plugin.slug for plugin in result.loaded_plugins] == ["payu"]
    assert result.failed_plugins[0].slug == "brokenpay"
    assert result.failed_plugins[0].stage == "factory"


def test_load_provider_plugins_strict_mode_raises_on_failed_plugin(
    monkeypatch,
):
    def fake_entry_points(*, group: str):
        assert group == "getpaid.simulator.providers"
        return [
            _entry_point(
                "brokenpay",
                lambda: (_ for _ in ()).throw(RuntimeError("bad plugin")),
            )
        ]

    monkeypatch.setattr(plugins, "entry_points", fake_entry_points)

    with pytest.raises(plugins.PluginLoadError):
        plugins.load_provider_plugins(
            SimulatorConfig(plugin_failure_mode="strict")
        )


def test_load_provider_plugins_rejects_incompatible_api_version(monkeypatch):
    def fake_entry_points(*, group: str):
        assert group == "getpaid.simulator.providers"
        return [
            _entry_point(
                "payu",
                lambda: _plugin("payu", api_version="999"),
            )
        ]

    monkeypatch.setattr(plugins, "entry_points", fake_entry_points)

    result = plugins.load_provider_plugins(
        SimulatorConfig(plugin_failure_mode="warn")
    )

    assert result.loaded_plugins == ()
    assert result.failed_plugins[0].slug == "payu"
    assert result.failed_plugins[0].stage == "compatibility"
