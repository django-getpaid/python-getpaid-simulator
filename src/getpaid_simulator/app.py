"""Litestar application for payment gateway simulator."""

import logging
from pathlib import Path

from litestar import Litestar
from litestar import get
from litestar.contrib.jinja import JinjaTemplateEngine
from litestar.datastructures import State
from litestar.template.config import TemplateConfig

from getpaid_simulator.core.config import SimulatorConfig
from getpaid_simulator.core.discovery import discover_providers
from getpaid_simulator.core.state import PaymentStateMachine
from getpaid_simulator.core.storage import SimulatorStorage
from getpaid_simulator.core.webhooks import WebhookDelivery
from getpaid_simulator.providers.paynow import routes as paynow_routes
from getpaid_simulator.providers.payu import routes as payu_routes
from getpaid_simulator.ui import routes as ui_routes


logger = logging.getLogger(__name__)


PAYU_ROUTE_HANDLERS = [
    payu_routes.oauth_endpoint,
    payu_routes.test_protected_endpoint,
    payu_routes.create_order,
    payu_routes.get_order_info,
    payu_routes.cancel_order,
    payu_routes.capture_order,
    payu_routes.create_refund,
]

PAYNOW_ROUTE_HANDLERS = [
    paynow_routes.create_payment,
    paynow_routes.get_payment_status,
    paynow_routes.get_payment_methods,
    paynow_routes.create_refund,
    paynow_routes.get_refund_status,
    paynow_routes.cancel_refund,
]


PROVIDER_ROUTES = {
    "payu": {
        "prefix": "/payu",
        "routes": PAYU_ROUTE_HANDLERS,
        "display_name": "PayU",
    },
    "paynow": {
        "prefix": "/paynow",
        "routes": PAYNOW_ROUTE_HANDLERS,
        "display_name": "PayNow",
    },
}


@get("/")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "service": "getpaid-simulator"}


def create_app() -> Litestar:
    discovered_providers = discover_providers()
    route_handlers = [health]
    provider_display_names: list[str] = []
    for provider_slug in discovered_providers:
        provider_config = PROVIDER_ROUTES.get(provider_slug)
        if provider_slug == "payu":
            route_handlers.extend(PAYU_ROUTE_HANDLERS)
        elif provider_slug == "paynow":
            route_handlers.extend(PAYNOW_ROUTE_HANDLERS)

        if provider_config is None:
            provider_display_names.append(provider_slug.title())
            continue
        provider_display_names.append(str(provider_config["display_name"]))

    route_handlers.extend(
        [
            getattr(ui_routes, "dashboard"),
            getattr(ui_routes, "payu_authorize_get"),
            getattr(ui_routes, "payu_authorize_post"),
            getattr(ui_routes, "paynow_authorize_get"),
            getattr(ui_routes, "paynow_authorize_post"),
        ]
    )

    logger.info(
        "Discovered providers: %s",
        ", ".join(provider_display_names),
    )

    storage = SimulatorStorage()
    config = SimulatorConfig.from_env()
    webhook_delivery = WebhookDelivery(
        storage=storage,
        second_key=config.payu_second_key,
    )
    state = State(
        {
            "storage": storage,
            "state_machine": PaymentStateMachine(storage),
            "webhook_delivery": webhook_delivery,
            "config": config,
            "discovered_providers": discovered_providers,
        }
    )

    return Litestar(
        route_handlers=route_handlers,
        state=state,
        template_config=TemplateConfig(
            engine=JinjaTemplateEngine(
                directory=Path(__file__).parent / "ui" / "templates"
            )
        ),
    )


app = create_app()
