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
    _allowed_transitions: dict[str, set[str]] = {
        "NEW": {"PENDING"},
        "PENDING": {"WAITING_FOR_CONFIRMATION", "CANCELED"},
        "WAITING_FOR_CONFIRMATION": {"COMPLETED", "CANCELED"},
        "COMPLETED": set(),
        "CANCELED": set(),
    }

    def __init__(self, storage: SimulatorStorage):
        self.storage = storage

    def transition(self, order_id: str, new_status: str) -> dict[str, Any]:
        order = self.storage.get_order(order_id)
        if order is None:
            raise KeyError(order_id)

        current_status = str(order.get("status", "NEW"))
        if new_status not in self._allowed_transitions.get(
            current_status, set()
        ):
            raise InvalidTransitionError(current_status, new_status)

        self.storage.update_order(order_id, status=new_status)
        updated_order = self.storage.get_order(order_id)
        if updated_order is None:
            raise KeyError(order_id)
        return updated_order
