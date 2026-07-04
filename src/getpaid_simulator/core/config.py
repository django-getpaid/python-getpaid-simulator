"""Configuration system for getpaid-simulator."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal


PluginFailureMode = Literal["strict", "warn"]


@dataclass
class SimulatorConfig:
    """Configuration for the payment simulator.

    All configuration values can be overridden via environment variables
    with the SIMULATOR_ prefix.
    """

    host: str = "0.0.0.0"
    port: int = 9000
    webhook_timeout: float = 5.0
    webhook_max_retries: int = 3
    log_level: str = "INFO"
    plugin_failure_mode: PluginFailureMode = "warn"

    @classmethod
    def from_env(cls) -> SimulatorConfig:
        """Load configuration from environment variables.

        Environment variables use the SIMULATOR_ prefix (e.g.,
        SIMULATOR_PORT=8080 overrides the port default).

        Returns:
            SimulatorConfig: Configuration instance with env var overrides.
        """
        plugin_failure_mode = os.environ.get(
            "SIMULATOR_PLUGIN_FAILURE_MODE", "warn"
        )
        if plugin_failure_mode not in {"strict", "warn"}:
            raise ValueError(
                "SIMULATOR_PLUGIN_FAILURE_MODE must be 'strict' or 'warn'"
            )

        return cls(
            host=os.environ.get("SIMULATOR_HOST", "0.0.0.0"),
            port=int(os.environ.get("SIMULATOR_PORT", "9000")),
            webhook_timeout=float(
                os.environ.get("SIMULATOR_WEBHOOK_TIMEOUT", "5.0")
            ),
            webhook_max_retries=int(
                os.environ.get("SIMULATOR_WEBHOOK_MAX_RETRIES", "3")
            ),
            log_level=os.environ.get("SIMULATOR_LOG_LEVEL", "INFO"),
            plugin_failure_mode=plugin_failure_mode,
        )
