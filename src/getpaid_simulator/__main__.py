"""CLI entry point for getpaid-simulator."""

import argparse
import sys

import uvicorn

from getpaid_simulator import __version__
from getpaid_simulator.app import create_app
from getpaid_simulator.core.config import SimulatorConfig
from getpaid_simulator.core.discovery import discover_providers


def _print_startup_banner(
    config: SimulatorConfig, discovered_providers: list[str]
) -> None:
    """Print startup banner with discovered providers and dashboard URL.

    Args:
        config: Simulator configuration.
        discovered_providers: List of discovered provider slugs.
    """
    # Map provider slugs to display names
    provider_display_names = {
        "payu": "PayU",
        "paynow": "PayNow",
    }

    providers_str = ", ".join(
        provider_display_names.get(slug, slug.title())
        for slug in discovered_providers
    )

    dashboard_url = f"http://{config.host}:{config.port}/sim/"

    banner = f"""
╔══════════════════════════════════════╗
║  🔶 getpaid-simulator v{__version__:<18}║
║  ⚠  SIMULATOR — NOT REAL PAYMENTS   ║
║                                      ║
║  Providers: {providers_str:<23}║
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

    # Discover providers and print startup banner
    discovered_providers = discover_providers()
    _print_startup_banner(config, discovered_providers)

    # Create and run app
    app = create_app()
    uvicorn.run(
        app,
        host=config.host,
        port=config.port,
        log_level=config.log_level.lower(),
    )


if __name__ == "__main__":
    main()
