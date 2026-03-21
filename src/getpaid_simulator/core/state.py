from __future__ import annotations

from typing import Any

from getpaid_simulator.core.storage import SimulatorStorage


class InvalidTransitionError(Exception):
    def __init__(self, current: str, requested: str):
        self.current = current
        self.requested = requested
        self.error_response = {
            "status": {
                "statusCode": "ERROR_VALUE_INVALID",
                "statusDesc": (
                    f"Cannot transition from {current} to {requested}"
                ),
            }
        }
        super().__init__(self.error_response["status"]["statusDesc"])


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

        provider = order.get("provider", "payu")
        transitions = self._provider_transitions.get(
            provider, self._default_transitions
        )

        current_status = str(order.get("status", "NEW"))
        if new_status not in transitions.get(current_status, set()):
            raise InvalidTransitionError(current_status, new_status)

        self.storage.update_order(order_id, status=new_status)
        updated_order = self.storage.get_order(order_id)
        if updated_order is None:
            raise KeyError(order_id)
        return updated_order
