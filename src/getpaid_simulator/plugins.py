"""Plugin loading for simulator provider integrations."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from dataclasses import field
from importlib.metadata import entry_points
from typing import Any

from getpaid_simulator.core.config import SimulatorConfig
from getpaid_simulator.spi import SIMULATOR_PLUGIN_API_VERSION
from getpaid_simulator.spi import SimulatorProviderPlugin


ENTRY_POINT_GROUP = "getpaid.simulator.providers"


@dataclass(frozen=True)
class ProviderLoadFailure:
    """Structured plugin load failure for logging and UI reporting."""

    slug: str
    stage: str
    error: str


@dataclass(frozen=True)
class PluginLoadResult:
    """Loaded plugins, failures, and validated provider configs."""

    loaded_plugins: tuple[SimulatorProviderPlugin, ...] = ()
    failed_plugins: tuple[ProviderLoadFailure, ...] = ()
    provider_configs: dict[str, Mapping[str, Any]] = field(default_factory=dict)


class PluginLoadError(RuntimeError):
    """Raised in strict mode when a simulator plugin cannot be loaded."""

    def __init__(self, failure: ProviderLoadFailure):
        self.failure = failure
        super().__init__(
            f"Failed to load simulator plugin {failure.slug!r} during "
            f"{failure.stage}: {failure.error}"
        )


def load_provider_plugins(
    config: SimulatorConfig,
    env: Mapping[str, str] | None = None,
) -> PluginLoadResult:
    """Load simulator provider plugins from entry points."""
    environment = env or os.environ
    loaded_plugins: list[SimulatorProviderPlugin] = []
    failed_plugins: list[ProviderLoadFailure] = []
    provider_configs: dict[str, Mapping[str, Any]] = {}

    for entry_point in sorted(
        entry_points(group=ENTRY_POINT_GROUP),
        key=lambda candidate: candidate.name,
    ):
        slug = entry_point.name or "<unknown>"

        try:
            plugin_factory = entry_point.load()
        except Exception as exc:
            _handle_failure(
                config=config,
                failed_plugins=failed_plugins,
                failure=ProviderLoadFailure(
                    slug=slug,
                    stage="import",
                    error=str(exc),
                ),
            )
            continue

        try:
            plugin = (
                plugin_factory() if callable(plugin_factory) else plugin_factory
            )
        except Exception as exc:
            _handle_failure(
                config=config,
                failed_plugins=failed_plugins,
                failure=ProviderLoadFailure(
                    slug=slug,
                    stage="factory",
                    error=str(exc),
                ),
            )
            continue

        failure = _validate_plugin(slug, plugin)
        if failure is not None:
            _handle_failure(
                config=config,
                failed_plugins=failed_plugins,
                failure=failure,
            )
            continue

        normalized_plugin = _normalize_plugin(plugin)

        try:
            provider_configs[normalized_plugin.slug] = dict(
                normalized_plugin.load_config(environment)
            )
        except Exception as exc:
            _handle_failure(
                config=config,
                failed_plugins=failed_plugins,
                failure=ProviderLoadFailure(
                    slug=normalized_plugin.slug,
                    stage="config",
                    error=str(exc),
                ),
            )
            continue

        loaded_plugins.append(normalized_plugin)

    return PluginLoadResult(
        loaded_plugins=tuple(loaded_plugins),
        failed_plugins=tuple(failed_plugins),
        provider_configs=provider_configs,
    )


def _validate_plugin(
    entry_point_slug: str,
    plugin: object,
) -> ProviderLoadFailure | None:
    required_fields = {
        "api_version",
        "slug",
        "display_name",
        "api_handlers",
        "ui_handlers",
        "transitions",
        "load_config",
    }
    missing_fields = [
        field_name
        for field_name in sorted(required_fields)
        if not hasattr(plugin, field_name)
    ]
    if missing_fields:
        return ProviderLoadFailure(
            slug=entry_point_slug,
            stage="factory",
            error=(
                "plugin object is missing required fields: "
                f"{', '.join(missing_fields)}"
            ),
        )

    plugin_api_version = str(getattr(plugin, "api_version"))
    plugin_slug = str(getattr(plugin, "slug"))
    if plugin_api_version != SIMULATOR_PLUGIN_API_VERSION:
        return ProviderLoadFailure(
            slug=plugin_slug,
            stage="compatibility",
            error=(
                "plugin API version "
                f"{plugin_api_version!r} is incompatible with host "
                f"{SIMULATOR_PLUGIN_API_VERSION!r}"
            ),
        )

    if plugin_slug != entry_point_slug:
        return ProviderLoadFailure(
            slug=entry_point_slug,
            stage="compatibility",
            error=(
                f"plugin slug {plugin_slug!r} does not match entry point "
                f"name {entry_point_slug!r}"
            ),
        )

    return None


def _normalize_plugin(plugin: object) -> SimulatorProviderPlugin:
    transitions = {
        str(status): set(next_statuses)
        for status, next_statuses in dict(
            getattr(plugin, "transitions")
        ).items()
    }
    authorize_path_template = getattr(plugin, "authorize_path_template", None)
    if authorize_path_template is not None:
        authorize_path_template = str(authorize_path_template)

    return SimulatorProviderPlugin(
        api_version=str(getattr(plugin, "api_version")),
        slug=str(getattr(plugin, "slug")),
        display_name=str(getattr(plugin, "display_name")),
        api_handlers=tuple(getattr(plugin, "api_handlers")),
        ui_handlers=tuple(getattr(plugin, "ui_handlers")),
        transitions=transitions,
        load_config=getattr(plugin, "load_config"),
        authorize_path_template=authorize_path_template,
    )


def _handle_failure(
    *,
    config: SimulatorConfig,
    failed_plugins: list[ProviderLoadFailure],
    failure: ProviderLoadFailure,
) -> None:
    if config.plugin_failure_mode == "strict":
        raise PluginLoadError(failure)
    failed_plugins.append(failure)
