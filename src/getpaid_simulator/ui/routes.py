from typing import Annotated, Optional

from litestar import get, post, Request
from litestar.enums import RequestEncodingType
from litestar.exceptions import HTTPException, NotFoundException
from litestar.params import Body
from litestar.response import Redirect, Template
from litestar.datastructures import State

from getpaid_simulator.core.state import PaymentStateMachine
from getpaid_simulator.core.storage import SimulatorStorage
from getpaid_simulator.providers.payu.webhooks import trigger_payu_webhook


@get(["/sim/", "/sim/dashboard"])
async def dashboard(state: State, provider: Optional[str] = None) -> Template:
    """Render payments dashboard."""
    storage: SimulatorStorage = state.storage
    if provider:
        orders_data = storage.list_orders_by_provider(provider)
    else:
        orders_data = storage.list_orders()

    orders = []
    for order in orders_data:
        amount_raw = order.get("totalAmount", 0)
        try:
            val = float(amount_raw) / 100
            formatted = f"{val:.2f} {order.get('currencyCode', 'PLN')}"
        except (ValueError, TypeError):
            formatted = str(amount_raw)

        orders.append(
            {
                "id": order["id"],
                "provider": order.get("provider", "payu"),
                "status": order.get("status", "NEW"),
                "formatted_amount": formatted,
            }
        )

    return Template(
        template_name="dashboard.html",
        context={
            "orders": orders,
            "current_provider": provider,
        },
    )


@get("/sim/payu/authorize/{order_id:str}")
async def payu_authorize_get(
    order_id: str,
    request: Request,
) -> Template:
    """Render authorization page for PayU."""
    storage: SimulatorStorage = request.app.state.storage

    order = storage.get_order(order_id)
    if not order:
        raise NotFoundException("Payment not found")

    if order.get("status") in ("COMPLETED", "CANCELED"):
        raise HTTPException(status_code=400, detail="Payment already processed")

    amount_raw = order.get("totalAmount", 0)
    try:
        amount_val = float(amount_raw) / 100
        formatted_amount = (
            f"{amount_val:.2f} {order.get('currencyCode', 'PLN')}"
        )
    except (ValueError, TypeError):
        formatted_amount = str(amount_raw)

    return Template(
        template_name="authorize.html",
        context={
            "provider": "PayU",
            "payment": order,
            "order_id": order_id,
            "amount": formatted_amount,
            "status": order.get("status", "NEW"),
        },
    )


@post("/sim/payu/authorize/{order_id:str}")
async def payu_authorize_post(
    order_id: str,
    request: Request,
    data: Annotated[
        dict[str, str], Body(media_type=RequestEncodingType.URL_ENCODED)
    ],
) -> Redirect:
    """Process authorization decision for PayU."""
    storage: SimulatorStorage = request.app.state.storage
    state_machine: PaymentStateMachine = request.app.state.state_machine

    order = storage.get_order(order_id)
    if not order:
        raise NotFoundException("Payment not found")

    current_status = order.get("status", "NEW")
    if current_status in ("COMPLETED", "CANCELED"):
        raise HTTPException(status_code=400, detail="Payment already processed")

    action = data.get("action")
    if action == "approve":
        if current_status == "NEW":
            state_machine.transition(order_id, "PENDING")
            state_machine.transition(order_id, "WAITING_FOR_CONFIRMATION")
        elif current_status == "PENDING":
            state_machine.transition(order_id, "WAITING_FOR_CONFIRMATION")
        state_machine.transition(order_id, "COMPLETED")
    elif action == "reject":
        if current_status == "NEW":
            state_machine.transition(order_id, "PENDING")
        state_machine.transition(order_id, "CANCELED")
    else:
        raise HTTPException(status_code=400, detail="Invalid action")

    await trigger_payu_webhook(order_id, storage, request.app.state.config)

    continue_url = order.get("continueUrl", "/")
    return Redirect(path=continue_url)


@get("/sim/paynow/authorize/{payment_id:str}")
async def paynow_authorize_get(
    payment_id: str,
    request: Request,
) -> Template:
    """Render authorization page for PayNow."""
    storage: SimulatorStorage = request.app.state.storage

    payment = storage.get_order(payment_id)
    if not payment:
        raise NotFoundException("Payment not found")

    if payment.get("status") in ("CONFIRMED", "REJECTED"):
        raise HTTPException(status_code=400, detail="Payment already processed")

    amount_raw = payment.get("amount", payment.get("totalAmount", 0))
    try:
        val = float(amount_raw) / 100
        formatted = f"{val:.2f} {payment.get('currency', payment.get('currencyCode', 'PLN'))}"
    except (ValueError, TypeError):
        formatted = str(amount_raw)

    return Template(
        template_name="authorize.html",
        context={
            "provider": "PayNow",
            "payment": payment,
            "payment_id": payment_id,
            "order_id": payment_id,
            "amount": formatted,
            "status": payment.get("status", "NEW"),
        },
    )


@post("/sim/paynow/authorize/{payment_id:str}")
async def paynow_authorize_post(
    payment_id: str,
    request: Request,
    data: Annotated[
        dict[str, str], Body(media_type=RequestEncodingType.URL_ENCODED)
    ],
) -> Redirect:
    """Process authorization decision for PayNow."""
    storage: SimulatorStorage = request.app.state.storage
    state_machine: PaymentStateMachine = request.app.state.state_machine

    payment = storage.get_order(payment_id)
    if not payment:
        raise NotFoundException("Payment not found")

    current_status = payment.get("status", "NEW")
    if current_status in ("CONFIRMED", "REJECTED"):
        raise HTTPException(status_code=400, detail="Payment already processed")

    action = data.get("action")
    if action == "approve":
        if current_status == "NEW":
            state_machine.transition(payment_id, "PENDING")
        state_machine.transition(payment_id, "CONFIRMED")
    elif action == "reject":
        if current_status == "NEW":
            state_machine.transition(payment_id, "PENDING")
        state_machine.transition(payment_id, "REJECTED")
    else:
        raise HTTPException(status_code=400, detail="Invalid action")

    # TODO: Add webhook callback later
    webhook_callback = getattr(request.app.state, "webhook_callback", None)
    if webhook_callback and callable(webhook_callback):
        webhook_callback(payment_id)

    continue_url = payment.get("continueUrl", "/sim/dashboard")
    return Redirect(path=continue_url)
