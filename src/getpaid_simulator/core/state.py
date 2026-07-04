from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any


if TYPE_CHECKING:
    from getpaid_simulator.core.storage import SimulatorStorage


class UnknownProviderError(LookupError):
    """Raised when an order's provider has no registered transitions."""

    def __init__(self, provider: str | None):
        self.provider = provider
        super().__init__(f"No transitions registered for provider {provider!r}")


class InvalidTransitionError(Exception):
    """Raised when a payment cannot move to the requested status.

    Carries provider-neutral fields (``code``, ``message``,
    ``current_state``, ``event``). Provider plugins own their wire
    formats and should render these fields into provider-specific
    error bodies themselves.
    """

    def __init__(self, current: str, requested: str):
        self.code = "INVALID_TRANSITION"
        self.current_state = current
        self.event = requested
        self.message = f"Cannot transition from {current} to {requested}"
        super().__init__(self.message)

    @property
    def current(self) -> str:
        """Legacy alias for :attr:`current_state` (pre-3.2 name)."""
        return self.current_state

    @property
    def requested(self) -> str:
        """Legacy alias for :attr:`event` (pre-3.2 name)."""
        return self.event

    @property
    def error_response(self) -> dict[str, Any]:
        """PayU-shaped error body.

        Deprecated: kept only because published PayU simulator plugins
        (``python-getpaid-payu`` <= 3.1.0) return this attribute
        verbatim on the wire. New plugins should render their own wire
        format from the neutral fields instead.
        """
        return {
            "status": {
                "statusCode": "ERROR_VALUE_INVALID",
                "statusDesc": self.message,
            }
        }


class PaymentStateMachine:
    def __init__(
        self,
        storage: SimulatorStorage,
        transitions: dict[str, set[str]] | None = None,
    ):
        self.storage = storage
        self._default_transitions = transitions or {}
        self._provider_transitions: dict[str, dict[str, set[str]]] = {}

    def register_provider(
        self,
        provider_slug: str,
        transitions: dict[str, set[str]],
    ) -> None:
        self._provider_transitions[provider_slug] = transitions

    def transition(self, order_id: str, new_status: str) -> dict[str, Any]:
        order = self.storage.get_order(order_id)
        if order is None:
            raise KeyError(order_id)

        provider = order.get("provider")
        transitions = self._provider_transitions.get(provider)
        if transitions is None:
            if not self._default_transitions:
                raise UnknownProviderError(provider)
            transitions = self._default_transitions

        current_status = str(order.get("status", "NEW"))
        if new_status not in transitions.get(current_status, set()):
            raise InvalidTransitionError(current_status, new_status)

        self.storage.update_order(order_id, status=new_status)
        updated_order = self.storage.get_order(order_id)
        if updated_order is None:
            raise KeyError(order_id)
        return updated_order
