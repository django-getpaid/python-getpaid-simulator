from decimal import Decimal
from decimal import InvalidOperation
from typing import Any
from typing import Optional

from litestar import get
from litestar.datastructures import State
from litestar.response import Template

from getpaid_simulator.core.storage import SimulatorStorage
from getpaid_simulator.plugins import ProviderLoadFailure
from getpaid_simulator.spi import SimulatorProviderPlugin


def _format_amount_for_display(
    order: dict[str, Any],
    provider_config: dict[str, Any] | None,
) -> str:
    amount_raw = order.get("amount", order.get("totalAmount", 0))
    currency = str(order.get("currency", order.get("currencyCode", "PLN")))
    try:
        amount_value = Decimal(str(amount_raw))
    except (InvalidOperation, TypeError, ValueError):
        return str(amount_raw)

    minor_unit_places = _minor_unit_places(provider_config)
    if minor_unit_places is not None:
        amount_value /= Decimal(10) ** minor_unit_places

    return f"{amount_value:.2f} {currency}"


def _minor_unit_places(provider_config: dict[str, Any] | None) -> int | None:
    if provider_config is None:
        return None

    raw_value = provider_config.get("amount_minor_unit_places")
    if raw_value is None:
        return None

    try:
        places = int(raw_value)
    except (TypeError, ValueError):
        return None

    if places < 0:
        return None

    return places


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
        provider_slug = str(order.get("provider", "unknown"))
        plugin = loaded_plugins.get(provider_slug)
        provider_config = state.provider_configs.get(provider_slug)
        orders.append(
            {
                "id": order["id"],
                "provider": provider_slug,
                "provider_display_name": (
                    plugin.display_name if plugin is not None else provider_slug
                ),
                "status": order.get("status", "NEW"),
                "formatted_amount": _format_amount_for_display(
                    order,
                    provider_config,
                ),
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
