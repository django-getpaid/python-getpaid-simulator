"""Litestar application for payment gateway simulator."""

from getpaid_simulator.core.config import SimulatorConfig
from getpaid_simulator.core.state import PaymentStateMachine
from getpaid_simulator.core.storage import SimulatorStorage
from getpaid_simulator.core.webhooks import WebhookDelivery
from getpaid_simulator.providers.payu import routes as payu_routes
from litestar import Litestar
from litestar import get
from litestar.datastructures import State


@get("/")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "service": "getpaid-simulator"}


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
    }
)

app = Litestar(
    route_handlers=[
        health,
        payu_routes.oauth_endpoint,
        payu_routes.test_protected_endpoint,
        payu_routes.create_order,
        payu_routes.get_order_info,
        payu_routes.cancel_order,
        payu_routes.capture_order,
        payu_routes.create_refund,
    ],
    state=state,
)
