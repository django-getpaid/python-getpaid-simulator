"""Litestar application for payment gateway simulator."""

from __future__ import annotations

import logging
from pathlib import Path

from litestar import Litestar
from litestar import get
from litestar.datastructures import State
from litestar.plugins.jinja import JinjaTemplateEngine
from litestar.static_files import create_static_files_router
from litestar.template.config import TemplateConfig

from getpaid_simulator.core.config import SimulatorConfig
from getpaid_simulator.core.state import InvalidTransitionError
from getpaid_simulator.core.state import PaymentStateMachine
from getpaid_simulator.core.storage import SimulatorStorage
from getpaid_simulator.core.webhooks import WebhookTransport
from getpaid_simulator.plugins import PluginLoadResult
from getpaid_simulator.plugins import load_provider_plugins
from getpaid_simulator.ui import routes as ui_routes


logger = logging.getLogger(__name__)


@get("/")
async def health(state: State) -> dict[str, object]:
    """Health check endpoint."""
    loaded_plugins = list(state.loaded_plugins)
    failed_plugins = [failure.slug for failure in state.failed_plugins]
    status = "degraded" if failed_plugins else "ok"
    return {
        "status": status,
        "service": "getpaid-simulator",
        "loadedProviders": loaded_plugins,
        "failedProviders": failed_plugins,
    }


@get("/sim/status")
async def simulator_status(state: State) -> dict[str, object]:
    """Detailed status endpoint for the simulator host."""
    return {
        "status": "degraded" if state.failed_plugins else "ok",
        "loadedProviders": [
            {
                "slug": slug,
                "displayName": plugin.display_name,
            }
            for slug, plugin in state.loaded_plugins.items()
        ],
        "failedProviders": [
            {
                "slug": failure.slug,
                "stage": failure.stage,
                "error": failure.error,
            }
            for failure in state.failed_plugins
        ],
    }


def create_app(
    config: SimulatorConfig | None = None,
    plugin_load_result: PluginLoadResult | None = None,
) -> Litestar:
    config = config or SimulatorConfig.from_env()
    plugin_load_result = plugin_load_result or load_provider_plugins(config)
    loaded_plugins = {
        plugin.slug: plugin for plugin in plugin_load_result.loaded_plugins
    }
    state_machine = PaymentStateMachine(SimulatorStorage())
    for plugin in plugin_load_result.loaded_plugins:
        state_machine.register_provider(plugin.slug, plugin.transitions)

    route_handlers = [health, simulator_status, ui_routes.dashboard]
    for plugin in plugin_load_result.loaded_plugins:
        route_handlers.extend(plugin.api_handlers)
        route_handlers.extend(plugin.ui_handlers)

    loaded_display_names = [
        plugin.display_name for plugin in plugin_load_result.loaded_plugins
    ]
    failed_slugs = [
        failure.slug for failure in plugin_load_result.failed_plugins
    ]
    if loaded_display_names:
        logger.info(
            "Loaded simulator plugins: %s",
            ", ".join(loaded_display_names),
        )
    else:
        logger.info("Loaded simulator plugins: none")
    if failed_slugs:
        logger.warning(
            "Failed simulator plugins: %s",
            ", ".join(failed_slugs),
        )

    storage = state_machine.storage
    webhook_transport = WebhookTransport(
        timeout=config.webhook_timeout,
        max_retries=config.webhook_max_retries,
    )
    state = State(
        {
            "storage": storage,
            "state_machine": state_machine,
            "webhook_transport": webhook_transport,
            "config": config,
            "loaded_plugins": loaded_plugins,
            "provider_configs": plugin_load_result.provider_configs,
            "failed_plugins": plugin_load_result.failed_plugins,
            "invalid_transition_error": InvalidTransitionError,
        }
    )
    static_files_router = create_static_files_router(
        path="/static",
        directories=[Path(__file__).parent / "ui" / "static"],
    )

    return Litestar(
        route_handlers=[*route_handlers, static_files_router],
        state=state,
        template_config=TemplateConfig(
            engine=JinjaTemplateEngine(
                directory=Path(__file__).parent / "ui" / "templates"
            )
        ),
    )
