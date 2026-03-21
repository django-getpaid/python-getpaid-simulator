from typing import Optional

from litestar import get
from litestar.datastructures import State
from litestar.response import Template

from getpaid_simulator.core.storage import SimulatorStorage
from getpaid_simulator.plugins import ProviderLoadFailure
from getpaid_simulator.spi import SimulatorProviderPlugin


@get(["/sim/", "/sim/dashboard"])
async def dashboard(state: State, provider: Optional[str] = None) -> Template:
    """Render payments dashboard."""
    storage: SimulatorStorage = state.storage
    loaded_plugins: dict[str, SimulatorProviderPlugin] = state.loaded_plugins
    failed_plugins: tuple[ProviderLoadFailure, ...] = state.failed_plugins
    if provider:
        orders_data = storage.list_orders_by_provider(provider)
    else:
        orders_data = storage.list_orders()

    provider_filters = [
        {
            "slug": slug,
            "display_name": plugin.display_name,
        }
        for slug, plugin in loaded_plugins.items()
    ]

    orders = []
    for order in orders_data:
        amount_raw = order.get("amount", order.get("totalAmount", 0))
        currency = order.get("currency", order.get("currencyCode", "PLN"))
        try:
            val = float(amount_raw) / 100
            formatted = f"{val:.2f} {currency}"
        except (ValueError, TypeError):
            formatted = str(amount_raw)

        provider_slug = str(order.get("provider", "unknown"))
        plugin = loaded_plugins.get(provider_slug)
        orders.append(
            {
                "id": order["id"],
                "provider": provider_slug,
                "provider_display_name": (
                    plugin.display_name if plugin is not None else provider_slug
                ),
                "status": order.get("status", "NEW"),
                "formatted_amount": formatted,
                "authorize_url": (
                    plugin.build_authorize_path(str(order["id"]))
                    if plugin is not None
                    else None
                ),
            }
        )

    return Template(
        template_name="dashboard.html",
        context={
            "orders": orders,
            "current_provider": provider,
            "provider_filters": provider_filters,
            "failed_plugins": failed_plugins,
        },
    )
