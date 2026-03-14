"""Configuration system for getpaid-simulator."""

import os
from dataclasses import dataclass


@dataclass
class SimulatorConfig:
    """Configuration for the payment simulator.

    All configuration values can be overridden via environment variables
    with the SIMULATOR_ prefix.
    """

    host: str = "0.0.0.0"
    port: int = 9000
    payu_second_key: str = "b6ca15b0d1020e8094d9b5f8d163db54"
    paynow_signature_key: str = "sim-paynow-key-default"
    paynow_api_key: str = "sim-paynow-api-key"
    paynow_notify_url: str = ""
    webhook_timeout: float = 5.0
    webhook_max_retries: int = 3
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "SimulatorConfig":
        """Load configuration from environment variables.

        Environment variables use the SIMULATOR_ prefix (e.g.,
        SIMULATOR_PORT=8080 overrides the port default).

        Returns:
            SimulatorConfig: Configuration instance with env var overrides.
        """
        return cls(
            host=os.environ.get("SIMULATOR_HOST", "0.0.0.0"),
            port=int(os.environ.get("SIMULATOR_PORT", "9000")),
            payu_second_key=os.environ.get(
                "SIMULATOR_PAYU_SECOND_KEY",
                "b6ca15b0d1020e8094d9b5f8d163db54",
            ),
            paynow_signature_key=os.environ.get(
                "SIMULATOR_PAYNOW_SIGNATURE_KEY",
                "sim-paynow-key-default",
            ),
            paynow_api_key=os.environ.get(
                "SIMULATOR_PAYNOW_API_KEY",
                "sim-paynow-api-key",
            ),
            paynow_notify_url=os.environ.get("SIMULATOR_PAYNOW_NOTIFY_URL", ""),
            webhook_timeout=float(
                os.environ.get("SIMULATOR_WEBHOOK_TIMEOUT", "5.0")
            ),
            webhook_max_retries=int(
                os.environ.get("SIMULATOR_WEBHOOK_MAX_RETRIES", "3")
            ),
            log_level=os.environ.get("SIMULATOR_LOG_LEVEL", "INFO"),
        )
