from __future__ import annotations

import logging
from typing import Any
from typing import TypedDict
from typing import cast

from getpaid_simulator.core.config import SimulatorConfig
from getpaid_simulator.core.storage import SimulatorStorage

from litestar import Request
from litestar import get
from litestar import post
from litestar.enums import MediaType
from litestar.response import Response


logger = logging.getLogger(__name__)

PAYNOW_STATUSES = {
    "NEW",
    "PENDING",
    "CONFIRMED",
    "REJECTED",
    "ERROR",
    "EXPIRED",
    "ABANDONED",
}


class PaynowError(TypedDict):
    errorType: str
    message: str


class PaynowErrorResponse(TypedDict):
    statusCode: int
    errors: list[PaynowError]


class BuyerData(TypedDict, total=False):
    email: str


class PaymentMethod(TypedDict):
    id: int
    name: str
    description: str
    image: str
    status: str
    authorizationType: str


class PaymentMethodGroup(TypedDict):
    type: str
    paymentMethods: list[PaymentMethod]


class CreatePaymentPayload(TypedDict, total=False):
    amount: int
    currency: str
    externalId: str
    description: str
    buyer: BuyerData
    status: str


PAYMENT_METHODS: list[PaymentMethodGroup] = [
    {
        "type": "PBL",
        "paymentMethods": [
            {
                "id": 2001,
                "name": "mTransfer",
                "description": "mBank",
                "image": "https://static.paynow.pl/payment-method-icons/2001.png",
                "status": "ENABLED",
                "authorizationType": "REDIRECT",
            }
        ],
    },
    {
        "type": "CARD",
        "paymentMethods": [
            {
                "id": 3001,
                "name": "Visa",
                "description": "Visa",
                "image": "https://static.paynow.pl/payment-method-icons/3001.png",
                "status": "ENABLED",
                "authorizationType": "REDIRECT",
            }
        ],
    },
    {
        "type": "BLIK",
        "paymentMethods": [
            {
                "id": 5001,
                "name": "BLIK",
                "description": "BLIK",
                "image": "https://static.paynow.pl/payment-method-icons/5001.png",
                "status": "ENABLED",
                "authorizationType": "CODE",
            }
        ],
    },
]


def _error_response(
    status_code: int,
    error_type: str,
    message: str,
) -> Response[object]:
    return Response(
        content={
            "statusCode": status_code,
            "errors": [{"errorType": error_type, "message": message}],
        },
        status_code=status_code,
        media_type=MediaType.JSON,
    )


def _warn_if_signature_missing(request: Request[Any, Any, Any]) -> None:
    if request.headers.get("signature"):
        return
    logger.warning("Signature header missing for PayNow request")


def _validate_create_payload(payload: object) -> list[str]:
    if not isinstance(payload, dict):
        return ["Request body must be an object"]

    typed_payload = cast(CreatePaymentPayload, cast(object, payload))

    required_fields = [
        "amount",
        "currency",
        "externalId",
        "description",
        "buyer",
    ]
    errors = [
        f"Field '{field_name}' is required"
        for field_name in required_fields
        if field_name not in typed_payload
    ]

    buyer = typed_payload.get("buyer")
    if "buyer" in typed_payload and (
        not isinstance(buyer, dict) or not buyer.get("email")
    ):
        errors.append("Field 'buyer.email' is required")

    amount = typed_payload.get("amount")
    if "amount" in typed_payload and not isinstance(amount, int):
        errors.append("Field 'amount' must be an integer")

    status = typed_payload.get("status", "NEW")
    if status not in PAYNOW_STATUSES:
        errors.append("Field 'status' has invalid value")
    return errors


@post("/v3/payments")
async def create_payment(
    request: Request[Any, Any, Any],
) -> Response[object]:
    _warn_if_signature_missing(request)

    payload_object: object = await request.json()
    validation_errors = _validate_create_payload(payload_object)
    if validation_errors:
        return _error_response(400, "VALIDATION_ERROR", validation_errors[0])

    payload = cast(CreatePaymentPayload, payload_object)
    payment_data = dict(payload)
    payment_data["status"] = str(payload.get("status", "NEW"))

    config = cast(SimulatorConfig, request.app.state.config)
    notify_url = config.paynow_notify_url
    if notify_url:
        payment_data["notifyUrl"] = notify_url

    storage = cast(SimulatorStorage, request.app.state.storage)
    payment_id = storage.create_order(
        payment_data,
        provider="paynow",
    )

    host = request.headers.get("host", "localhost")
    redirect_url = f"http://{host}/sim/paynow/authorize/{payment_id}"
    response_body = {
        "redirectUrl": redirect_url,
        "paymentId": payment_id,
        "status": payment_data["status"],
    }
    return Response(
        content=response_body,
        status_code=201,
        media_type=MediaType.JSON,
    )


@get("/v3/payments/{payment_id:str}/status")
async def get_payment_status(
    request: Request[Any, Any, Any],
    payment_id: str,
) -> Response[object]:
    _warn_if_signature_missing(request)

    storage = cast(SimulatorStorage, request.app.state.storage)
    payment = storage.get_order(payment_id)
    if payment is None or payment.get("provider") != "paynow":
        return _error_response(
            404,
            "NOT_FOUND",
            f"Payment {payment_id} not found",
        )

    return Response(
        content={
            "paymentId": payment_id,
            "status": str(payment.get("status", "NEW")),
        },
        status_code=200,
        media_type=MediaType.JSON,
    )


@get("/v3/payments/paymentmethods")
async def get_payment_methods(
    request: Request[Any, Any, Any],
) -> Response[object]:
    _warn_if_signature_missing(request)
    return Response(
        content=PAYMENT_METHODS,
        status_code=200,
        media_type=MediaType.JSON,
    )


@post("/v3/payments/{payment_id:str}/refunds")
async def create_refund(
    request: Request[Any, Any, Any],
    payment_id: str,
) -> Response[object]:
    _warn_if_signature_missing(request)

    storage = cast(SimulatorStorage, request.app.state.storage)
    payment = storage.get_order(payment_id)
    if payment is None or payment.get("provider") != "paynow":
        return _error_response(
            404,
            "NOT_FOUND",
            f"Payment {payment_id} not found",
        )

    payment_status = payment.get("status", "NEW")
    if payment_status != "CONFIRMED":
        return _error_response(
            400,
            "VALIDATION_ERROR",
            f"Payment not in CONFIRMED status (current: {payment_status})",
        )

    payload = await request.json()
    if not isinstance(payload, dict):
        payload = {}

    amount = payload.get("amount")
    reason = payload.get("reason")

    if amount is None:
        return _error_response(
            400,
            "VALIDATION_ERROR",
            "Field 'amount' is required",
        )

    refund_data = {
        "amount": amount,
        "status": "SUCCESSFUL",
    }
    if reason is not None:
        refund_data["reason"] = reason

    refund_id = storage.create_refund(payment_id, refund_data)

    response_body = {
        "refundId": refund_id,
        "status": "SUCCESSFUL",
    }
    return Response(
        content=response_body,
        status_code=201,
        media_type=MediaType.JSON,
    )


@get("/v3/refunds/{refund_id:str}/status")
async def get_refund_status(
    request: Request[Any, Any, Any],
    refund_id: str,
) -> Response[object]:
    _warn_if_signature_missing(request)

    storage = cast(SimulatorStorage, request.app.state.storage)
    refund = storage.get_refund(refund_id)
    if refund is None:
        return _error_response(
            404,
            "NOT_FOUND",
            f"Refund {refund_id} not found",
        )

    amount = refund.get("amount")
    if isinstance(amount, str):
        amount = int(amount)

    response_body = {
        "refundId": refund_id,
        "status": str(refund.get("status", "SUCCESSFUL")),
        "amount": amount,
    }
    return Response(
        content=response_body,
        status_code=200,
        media_type=MediaType.JSON,
    )


@post("/v3/refunds/{refund_id:str}/cancel")
async def cancel_refund(
    request: Request[Any, Any, Any],
    refund_id: str,
) -> Response[object]:
    _warn_if_signature_missing(request)

    storage = cast(SimulatorStorage, request.app.state.storage)
    refund = storage.get_refund(refund_id)
    if refund is None:
        return _error_response(
            404,
            "NOT_FOUND",
            f"Refund {refund_id} not found",
        )

    storage.update_refund(refund_id, status="CANCELLED")

    response_body = {
        "refundId": refund_id,
        "status": "CANCELLED",
    }
    return Response(
        content=response_body,
        status_code=200,
        media_type=MediaType.JSON,
    )
