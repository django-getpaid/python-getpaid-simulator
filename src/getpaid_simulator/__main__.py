"""CLI entry point for getpaid-simulator."""

import argparse
import sys

import uvicorn

from getpaid_simulator import __version__
from getpaid_simulator.app import create_app
from getpaid_simulator.core.config import SimulatorConfig
from getpaid_simulator.plugins import load_provider_plugins


def _print_startup_banner(
    config: SimulatorConfig,
    loaded_providers: list[str],
    failed_providers: list[str],
) -> None:
    """Print startup banner with discovered providers and dashboard URL.

    Args:
        config: Simulator configuration.
        loaded_providers: Display names for loaded simulator plugins.
        failed_providers: Slugs for failed plugins.
    """
    providers_str = ", ".join(loaded_providers) if loaded_providers else "none"
    failed_str = ", ".join(failed_providers) if failed_providers else "none"

    dashboard_url = f"http://{config.host}:{config.port}/sim/"
    status_label = "DEGRADED" if failed_providers else "READY"

    banner = f"""
╔══════════════════════════════════════╗
║  🔶 getpaid-simulator v{__version__:<18}║
║  ⚠  SIMULATOR — NOT REAL PAYMENTS   ║
║  Status: {status_label:<27}║
║  Providers: {providers_str:<23}║
║  Failed: {failed_str:<26}║
║  Dashboard: {dashboard_url:<23}║
╚══════════════════════════════════════╝
"""
    print(banner)


def main() -> None:
    """CLI entry point for getpaid-simulator."""
    parser = argparse.ArgumentParser(
        description="GetPaid Payment Gateway Simulator",
        prog="getpaid-simulator",
    )
    parser.add_argument(
        "--host",
        default=None,
        help="Server host (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Server port (default: 9000)",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default=None,
        help="Logging level (default: INFO)",
    )
    parser.add_argument(
        "--plugin-failure-mode",
        choices=["strict", "warn"],
        default=None,
        help="Plugin failure mode (default: warn)",
    )

    args = parser.parse_args()

    # Load config from environment variables
    config = SimulatorConfig.from_env()

    # Override with CLI arguments if provided
    if args.host is not None:
        config.host = args.host
    if args.port is not None:
        config.port = args.port
    if args.log_level is not None:
        config.log_level = args.log_level
    if args.plugin_failure_mode is not None:
        config.plugin_failure_mode = args.plugin_failure_mode

    plugin_load_result = load_provider_plugins(config)
    _print_startup_banner(
        config,
        loaded_providers=[
            plugin.display_name for plugin in plugin_load_result.loaded_plugins
        ],
        failed_providers=[
            failure.slug for failure in plugin_load_result.failed_plugins
        ],
    )

    # Create and run app
    app = create_app(config, plugin_load_result)
    uvicorn.run(
        app,
        host=config.host,
        port=config.port,
        log_level=config.log_level.lower(),
    )


if __name__ == "__main__":
    main()
