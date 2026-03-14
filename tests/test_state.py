import pytest

from getpaid_simulator.core.state import InvalidTransitionError
from getpaid_simulator.core.state import PaymentStateMachine
from getpaid_simulator.core.storage import SimulatorStorage


@pytest.fixture
def storage() -> SimulatorStorage:
    return SimulatorStorage()


@pytest.fixture
def state_machine(storage: SimulatorStorage) -> PaymentStateMachine:
    return PaymentStateMachine(storage)


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
