from datetime import UTC
from datetime import datetime
from datetime import timedelta
from decimal import Decimal

import pytest

from getpaid_simulator.core.storage import SimulatorStorage


def test_order_create_get_update_and_list():
    storage = SimulatorStorage()

    order_id = storage.create_order(
        {
            "provider": "payu",
            "status": "NEW",
            "totalAmount": 12345,
            "products": [{"name": "Starter", "unitPrice": 999}],
        }
    )

    created_order = storage.get_order(order_id)
    assert created_order is not None
    assert created_order["id"] == order_id
    assert created_order["status"] == "NEW"
    assert created_order["totalAmount"] == "12345"
    assert created_order["products"][0]["unitPrice"] == "999"

    storage.update_order(order_id, status="PENDING", totalAmount=456)
    updated_order = storage.get_order(order_id)
    assert updated_order is not None
    assert updated_order["status"] == "PENDING"
    assert updated_order["totalAmount"] == "456"

    orders = storage.list_orders()
    assert len(orders) == 1
    assert orders[0]["id"] == order_id


def test_create_order_requires_provider():
    """Orders must never silently default to a provider."""
    storage = SimulatorStorage()

    with pytest.raises(TypeError, match="provider"):
        storage.create_order({"status": "NEW", "totalAmount": "100"})


def test_create_order_keeps_provider_from_data():
    storage = SimulatorStorage()

    order_id = storage.create_order(
        {"provider": "paynow", "status": "NEW", "totalAmount": "100"}
    )

    order = storage.get_order(order_id)
    assert order is not None
    assert order["provider"] == "paynow"


def test_decimal_amounts_round_half_up_instead_of_truncating():
    storage = SimulatorStorage()

    order_id = storage.create_order(
        {
            "provider": "payu",
            "status": "NEW",
            "totalAmount": Decimal("1234.5"),
            "fraction": Decimal("10.4"),
        }
    )

    order = storage.get_order(order_id)
    assert order is not None
    assert order["totalAmount"] == "1235"
    assert order["fraction"] == "10"


def test_get_order_returns_none_for_missing_order():
    storage = SimulatorStorage()
    assert storage.get_order("missing") is None


def test_token_lifecycle_valid_and_expired():
    storage = SimulatorStorage()

    token_data = storage.create_token("145227")
    token = token_data["access_token"]

    assert token_data["expires_in"] == 3600
    assert storage.validate_token(token) is True
    assert storage.validate_token("missing") is False

    storage._tokens[token]["expires_at"] = datetime.now(UTC) - timedelta(
        seconds=1
    )
    assert storage.validate_token(token) is False


def test_expired_tokens_are_purged_on_validate_and_create():
    storage = SimulatorStorage()

    stale = storage.create_token("145227")["access_token"]
    storage._tokens[stale]["expires_at"] = datetime.now(UTC) - timedelta(
        seconds=1
    )

    # Validation of any token purges expired entries.
    assert storage.validate_token(stale) is False
    assert stale not in storage._tokens

    other_stale = storage.create_token("145227")["access_token"]
    storage._tokens[other_stale]["expires_at"] = datetime.now(UTC) - timedelta(
        seconds=1
    )

    # Creating a new token also purges expired entries.
    storage.create_token("145227")
    assert other_stale not in storage._tokens


def test_refund_create_and_get_refunds_for_order():
    storage = SimulatorStorage()
    order_id = storage.create_order(
        {"provider": "payu", "status": "NEW", "totalAmount": "1000"}
    )

    refund_id = storage.create_refund(
        order_id,
        {"status": "PENDING", "amount": 321, "description": "Partial"},
    )

    refunds = storage.get_refunds(order_id)
    assert len(refunds) == 1
    assert refunds[0]["id"] == refund_id
    assert refunds[0]["order_id"] == order_id
    assert refunds[0]["amount"] == "321"
    assert refunds[0]["status"] == "PENDING"


def test_get_refunds_returns_empty_for_unknown_order():
    storage = SimulatorStorage()
    assert storage.get_refunds("missing") == []


def test_storage_provider_field():
    storage = SimulatorStorage()

    payu_order_id = storage.create_order(
        provider="payu",
        total_amount=1000,
        currency="PLN",
        description="PayU order",
        notify_url="https://merchant.example/payu/notify",
        continue_url="https://merchant.example/continue",
        buyer_email="payu@example.com",
    )
    paynow_order_id = storage.create_order(
        provider="paynow",
        total_amount=2000,
        currency="PLN",
        description="PayNow order",
        continue_url="https://merchant.example/continue",
        buyer_email="paynow@example.com",
    )

    payu_order = storage.get_order(payu_order_id)
    paynow_order = storage.get_order(paynow_order_id)

    assert payu_order is not None
    assert paynow_order is not None
    assert payu_order["provider"] == "payu"
    assert paynow_order["provider"] == "paynow"


def test_storage_list_by_provider():
    storage = SimulatorStorage()

    storage.create_order(
        provider="payu",
        total_amount=1000,
        currency="PLN",
        description="PayU one",
        notify_url="https://merchant.example/payu/notify",
        continue_url="https://merchant.example/continue",
        buyer_email="payu1@example.com",
    )
    storage.create_order(
        provider="payu",
        total_amount=1100,
        currency="PLN",
        description="PayU two",
        notify_url="https://merchant.example/payu/notify",
        continue_url="https://merchant.example/continue",
        buyer_email="payu2@example.com",
    )
    storage.create_order(
        provider="paynow",
        total_amount=2000,
        currency="PLN",
        description="PayNow",
        continue_url="https://merchant.example/continue",
        buyer_email="paynow@example.com",
    )

    payu_orders = storage.list_orders_by_provider("payu")
    paynow_orders = storage.list_orders_by_provider("paynow")

    assert len(payu_orders) == 2
    assert all(order["provider"] == "payu" for order in payu_orders)
    assert len(paynow_orders) == 1
    assert paynow_orders[0]["provider"] == "paynow"
