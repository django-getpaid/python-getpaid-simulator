from __future__ import annotations

from getpaid_simulator.core.config import SimulatorConfig
from getpaid_simulator.plugins import load_provider_plugins


ENTRY_POINT_GROUP = "getpaid.simulator.providers"


def discover_providers() -> list[str]:
    result = load_provider_plugins(SimulatorConfig())
    return [plugin.slug for plugin in result.loaded_plugins]
