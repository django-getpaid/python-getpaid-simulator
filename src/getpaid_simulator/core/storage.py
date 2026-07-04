from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from decimal import ROUND_HALF_UP
from decimal import Decimal
from typing import Any
from uuid import uuid4


def _centify(value: Any) -> Any:
    """Normalize numeric amounts to strings of integer minor units.

    Convention: callers pass amounts already expressed in the
    provider's minor unit (e.g. grosze for PLN), and stored payloads
    keep them as decimal strings — mirroring how PayU/PayNow put
    amounts on the wire. Decimals are rounded half-up to the nearest
    integer, never truncated.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return str(value)
    if isinstance(value, Decimal):
        return str(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    if isinstance(value, list):
        return [_centify(item) for item in value]
    if isinstance(value, dict):
        return {key: _centify(item) for key, item in value.items()}
    return value


def _centify_dict(data: dict[str, Any]) -> dict[str, Any]:
    return _centify(data)


class SimulatorStorage:
    def __init__(self) -> None:
        self._orders: dict[str, dict[str, Any]] = {}
        self._tokens: dict[str, dict[str, Any]] = {}
        self._refunds: defaultdict[str, list[dict[str, Any]]] = defaultdict(
            list
        )

    def create_order(
        self,
        data: dict[str, Any] | None = None,
        *,
        provider: str | None = None,
        total_amount: int | str | Decimal | None = None,
        currency: str | None = None,
        description: str | None = None,
        notify_url: str = "",
        continue_url: str | None = None,
        buyer_email: str | None = None,
    ) -> str:
        order_id = uuid4().hex
        if data is None:
            if provider is None:
                raise TypeError(
                    "provider is required when data is not provided"
                )
            if total_amount is None:
                raise TypeError(
                    "total_amount is required when data is not provided"
                )
            if currency is None:
                raise TypeError(
                    "currency is required when data is not provided"
                )
            if description is None:
                raise TypeError(
                    "description is required when data is not provided"
                )

            order_payload: dict[str, Any] = {
                "provider": provider,
                "status": "NEW",
                "totalAmount": total_amount,
                "currencyCode": currency,
                "description": description,
                "continueUrl": continue_url,
                "buyer": {},
            }
            if notify_url:
                order_payload["notifyUrl"] = notify_url
            if buyer_email:
                order_payload["buyer"] = {"email": buyer_email}
        else:
            order_payload = deepcopy(data)
            data_provider = provider or order_payload.get("provider")
            if data_provider is None:
                raise TypeError(
                    "provider is required: pass provider= or include a "
                    "'provider' key in data"
                )
            order_payload["provider"] = str(data_provider)

        order_data = _centify_dict(order_payload)
        order_data["id"] = order_id
        self._orders[order_id] = order_data
        return order_id

    def get_order(self, order_id: str) -> dict[str, Any] | None:
        order = self._orders.get(order_id)
        if order is None:
            return None
        return deepcopy(order)

    def update_order(self, order_id: str, **updates) -> None:
        if order_id not in self._orders:
            raise KeyError(order_id)
        self._orders[order_id].update(_centify(deepcopy(updates)))

    def list_orders(self) -> list[dict[str, Any]]:
        return [deepcopy(order) for order in self._orders.values()]

    def list_orders_by_provider(self, provider: str) -> list[dict[str, Any]]:
        return [
            deepcopy(order)
            for order in self._orders.values()
            if order.get("provider") == provider
        ]

    def _purge_expired_tokens(self) -> None:
        now = datetime.now(UTC)
        expired = [
            token
            for token, token_data in self._tokens.items()
            if now >= token_data["expires_at"]
        ]
        for token in expired:
            del self._tokens[token]

    def create_token(
        self, pos_id: str, expires_in: int = 3600
    ) -> dict[str, Any]:
        self._purge_expired_tokens()
        access_token = uuid4().hex
        self._tokens[access_token] = {
            "pos_id": pos_id,
            "expires_at": datetime.now(UTC) + timedelta(seconds=expires_in),
        }
        return {"access_token": access_token, "expires_in": expires_in}

    def validate_token(self, token: str) -> bool:
        self._purge_expired_tokens()
        return token in self._tokens

    def create_refund(self, order_id: str, data: dict[str, Any]) -> str:
        refund_id = uuid4().hex
        refund_data = _centify_dict(deepcopy(data))
        refund_data["id"] = refund_id
        refund_data["order_id"] = order_id
        self._refunds[order_id].append(refund_data)
        return refund_id

    def get_refunds(self, order_id: str) -> list[dict[str, Any]]:
        return [deepcopy(refund) for refund in self._refunds.get(order_id, [])]

    def get_refund(self, refund_id: str) -> dict[str, Any] | None:
        for refunds in self._refunds.values():
            for refund in refunds:
                if refund.get("id") == refund_id:
                    return deepcopy(refund)
        return None

    def update_refund(self, refund_id: str, **updates: Any) -> None:
        for refunds in self._refunds.values():
            for refund in refunds:
                if refund.get("id") == refund_id:
                    refund.update(_centify(deepcopy(updates)))
                    return
        raise KeyError(refund_id)
