from __future__ import annotations

from typing import Any

from getpaid_simulator.core.storage import SimulatorStorage


PAYU_TRANSITIONS: dict[str, set[str]] = {
    "NEW": {"PENDING"},
    "PENDING": {"WAITING_FOR_CONFIRMATION", "CANCELED"},
    "WAITING_FOR_CONFIRMATION": {"COMPLETED", "CANCELED"},
    "COMPLETED": set(),
    "CANCELED": set(),
}

PAYNOW_TRANSITIONS: dict[str, set[str]] = {
    "NEW": {"PENDING", "ABANDONED"},
    "PENDING": {
        "CONFIRMED",
        "REJECTED",
        "ERROR",
        "EXPIRED",
        "ABANDONED",
    },
    "CONFIRMED": set(),
    "REJECTED": set(),
    "ERROR": set(),
    "EXPIRED": set(),
    "ABANDONED": set(),
}


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
        self._allowed_transitions = transitions or PAYU_TRANSITIONS
        self._provider_transitions = {
            "payu": PAYU_TRANSITIONS,
            "paynow": PAYNOW_TRANSITIONS,
        }

    def transition(self, order_id: str, new_status: str) -> dict[str, Any]:
        order = self.storage.get_order(order_id)
        if order is None:
            raise KeyError(order_id)

        provider = order.get("provider", "payu")
        transitions = self._provider_transitions.get(
            provider, self._allowed_transitions
        )

        current_status = str(order.get("status", "NEW"))
        if new_status not in transitions.get(current_status, set()):
            raise InvalidTransitionError(current_status, new_status)

        self.storage.update_order(order_id, status=new_status)
        updated_order = self.storage.get_order(order_id)
        if updated_order is None:
            raise KeyError(order_id)
        return updated_order
