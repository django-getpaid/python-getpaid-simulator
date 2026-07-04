"""Stable plugin API for simulator provider integrations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from typing import Any


if TYPE_CHECKING:
    from collections.abc import Callable
    from collections.abc import Mapping


SIMULATOR_PLUGIN_API_VERSION = "1"


@dataclass(frozen=True)
class SimulatorProviderPlugin:
    """Declarative simulator provider plugin descriptor."""

    api_version: str
    slug: str
    display_name: str
    api_handlers: tuple[Any, ...]
    ui_handlers: tuple[Any, ...]
    transitions: dict[str, set[str]]
    load_config: Callable[[Mapping[str, str]], Mapping[str, Any]]
    authorize_path_template: str | None = None

    def build_authorize_path(self, entity_id: str) -> str | None:
        """Return the provider-specific authorize URL for dashboard links."""
        if self.authorize_path_template is None:
            return None
        return self.authorize_path_template.format(entity_id=entity_id)
