import pytest

from getpaid_paynow.simulator.transitions import PAYNOW_TRANSITIONS
from getpaid_payu.simulator.transitions import PAYU_TRANSITIONS

from getpaid_simulator.core.state import InvalidTransitionError
from getpaid_simulator.core.state import PaymentStateMachine
from getpaid_simulator.core.storage import SimulatorStorage


@pytest.fixture
def storage() -> SimulatorStorage:
    return SimulatorStorage()


@pytest.fixture
def state_machine(storage: SimulatorStorage) -> PaymentStateMachine:
    machine = PaymentStateMachine(storage)
    machine.register_provider("payu", PAYU_TRANSITIONS)
    return machine


def test_valid_happy_path_transitions(state_machine: PaymentStateMachine):
    order_id = state_machine.storage.create_order(
        {"status": "NEW", "totalAmount": "1200"}
    )

    pending = state_machine.transition(order_id, "PENDING")
    waiting = state_machine.transition(order_id, "WAITING_FOR_CONFIRMATION")
    completed = state_machine.transition(order_id, "COMPLETED")

    assert pending["status"] == "PENDING"
    assert waiting["status"] == "WAITING_FOR_CONFIRMATION"
    assert completed["status"] == "COMPLETED"


@pytest.mark.parametrize(
    ("start_status", "target_status"),
    [
        ("PENDING", "CANCELED"),
        ("WAITING_FOR_CONFIRMATION", "CANCELED"),
    ],
)
def test_valid_cancellation_paths(
    storage: SimulatorStorage,
    state_machine: PaymentStateMachine,
    start_status: str,
    target_status: str,
):
    order_id = storage.create_order(
        {"status": start_status, "totalAmount": "2400"}
    )

    order = state_machine.transition(order_id, target_status)

    assert order["status"] == "CANCELED"


@pytest.mark.parametrize(
    ("start_status", "target_status"),
    [
        ("COMPLETED", "CANCELED"),
        ("CANCELED", "PENDING"),
        ("WAITING_FOR_CONFIRMATION", "PENDING"),
    ],
)
def test_invalid_transitions_raise_payu_error_response(
    storage: SimulatorStorage,
    state_machine: PaymentStateMachine,
    start_status: str,
    target_status: str,
):
    order_id = storage.create_order(
        {"status": start_status, "totalAmount": "999"}
    )

    with pytest.raises(InvalidTransitionError) as error_info:
        state_machine.transition(order_id, target_status)

    error = error_info.value
    assert error.current == start_status
    assert error.requested == target_status
    assert error.error_response == {
        "status": {
            "statusCode": "ERROR_VALUE_INVALID",
            "statusDesc": (
                f"Cannot transition from {start_status} to {target_status}"
            ),
        }
    }


def test_paynow_transitions(storage: SimulatorStorage):
    state_machine = PaymentStateMachine(storage)
    state_machine.register_provider("paynow", PAYNOW_TRANSITIONS)
    order_id = storage.create_order(
        provider="paynow",
        total_amount=999,
        currency="PLN",
        description="PayNow order",
        continue_url="https://merchant.example/continue",
        buyer_email="paynow@example.com",
    )

    pending_order = state_machine.transition(order_id, "PENDING")
    confirmed_order = state_machine.transition(order_id, "CONFIRMED")

    assert pending_order["status"] == "PENDING"
    assert confirmed_order["status"] == "CONFIRMED"


def test_paynow_rejects_waiting_for_confirmation(storage: SimulatorStorage):
    state_machine = PaymentStateMachine(storage)
    state_machine.register_provider("paynow", PAYNOW_TRANSITIONS)
    order_id = storage.create_order(
        provider="paynow",
        total_amount=999,
        currency="PLN",
        description="PayNow order",
        continue_url="https://merchant.example/continue",
        buyer_email="paynow@example.com",
    )

    state_machine.transition(order_id, "PENDING")

    with pytest.raises(InvalidTransitionError) as error_info:
        state_machine.transition(order_id, "WAITING_FOR_CONFIRMATION")

    assert error_info.value.current == "PENDING"
    assert error_info.value.requested == "WAITING_FOR_CONFIRMATION"
