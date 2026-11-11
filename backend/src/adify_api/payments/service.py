import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from adify_api.accounts.models import Account
from adify_api.core.config import get_settings
from adify_api.orders.models import Order, OrderStatus
from adify_api.payments.models import OPEN_PAYMENT_STATUSES, Payment, PaymentStatus
from adify_api.payments.mono import MonoClient, MonoError

logger = logging.getLogger(__name__)


class PaymentError(Exception):
    def __init__(self, status_code: int, type_: str, msg: str) -> None:
        super().__init__(msg)
        self.status_code = status_code
        self.type = type_
        self.msg = msg


def _aware(moment: datetime | None) -> datetime | None:
    # SQLite drops the zone of stored timestamps; every stored time is UTC.
    return moment.replace(tzinfo=UTC) if moment and moment.tzinfo is None else moment


def _parse_time(value: Any) -> datetime | None:
    try:
        return _aware(datetime.fromisoformat(value)) if isinstance(value, str) else None
    except ValueError:
        return None


async def latest_payment(session: AsyncSession, order_id: uuid.UUID) -> Payment | None:
    return await session.scalar(
        select(Payment)
        .where(Payment.order_id == order_id)
        .order_by(Payment.created_at.desc(), Payment.id)
        .limit(1)
    )


async def start_payment(
    session: AsyncSession, order: Order, account: Account, mono: MonoClient | None
) -> Payment:
    """FR-038: the customer pays an order awaiting payment; Mono holds the funds.

    An invoice that is still open is reused, so paying twice opens the same Mono page.
    """
    if account.id != order.customer_id:
        raise PaymentError(403, "not_order_customer", "Only the customer pays for an order.")
    if order.status != OrderStatus.AWAITING_PAYMENT:
        raise PaymentError(409, "order_not_awaiting_payment", "This order is not awaiting payment.")
    if mono is None:
        raise PaymentError(
            503, "payments_unavailable", "Payments are not available right now. Try again later."
        )
    current = await latest_payment(session, order.id)
    if current and current.status in OPEN_PAYMENT_STATUSES and current.amount == order.price:
        return current

    settings = get_settings()
    webhook_url = (
        f"{settings.api_public_url.rstrip('/')}/api/v1/payments/mono/webhook"
        if settings.api_public_url
        else None
    )
    try:
        invoice = await mono.create_hold_invoice(
            amount=order.price,
            reference=str(order.id),
            destination=f"Adify order: {order.listing.title}"[:280],
            redirect_url=f"{settings.web_base_url}/orders/{order.id}?payment=return",
            webhook_url=webhook_url,
        )
    except MonoError as error:
        logger.error("Mono invoice for order %s failed: %s", order.id, error)
        raise PaymentError(
            502, "payment_provider_error", "Mono could not start the payment. Try again shortly."
        ) from None
    payment = Payment(
        order_id=order.id,
        invoice_id=invoice["invoiceId"],
        page_url=invoice["pageUrl"],
        amount=order.price,
        status=PaymentStatus.CREATED,
        created_at=datetime.now(UTC),
    )
    session.add(payment)
    await session.commit()
    return payment


async def apply_invoice_update(session: AsyncSession, data: dict[str, Any]) -> Payment | None:
    """Record a Mono invoice status from a webhook or the status API.

    Mono does not guarantee webhook order, so an update older than the last applied one is
    skipped. ``hold`` moves an order awaiting payment to paid.
    """
    payment = await session.scalar(
        select(Payment).where(Payment.invoice_id == str(data.get("invoiceId")))
    )
    if payment is None:
        return None
    modified = _parse_time(data.get("modifiedDate"))
    applied = _aware(payment.provider_modified_at)
    if applied and modified and modified <= applied:
        return payment
    try:
        status = PaymentStatus(data.get("status"))
    except ValueError:
        logger.warning("Unknown Mono status %r for %s", data.get("status"), payment.invoice_id)
        return payment

    payment.status = status
    payment.failure_reason = data.get("failureReason")
    payment.provider_modified_at = modified
    if status == PaymentStatus.HOLD:
        order = await session.get(Order, payment.order_id)
        if order is not None and order.status == OrderStatus.AWAITING_PAYMENT:
            order.status = OrderStatus.PAID
            order.paid_at = datetime.now(UTC)
    await session.commit()
    return payment


async def sync_payment(session: AsyncSession, order: Order, mono: MonoClient | None) -> Payment:
    """The order's latest payment, refreshed from Mono's status API while it is open.

    This also covers environments where Mono cannot reach the webhook, such as localhost.
    """
    payment = await latest_payment(session, order.id)
    if payment is None:
        raise PaymentError(404, "payment_not_found", "This order has no payment yet.")
    if payment.status in OPEN_PAYMENT_STATUSES and mono is not None:
        try:
            await apply_invoice_update(session, await mono.invoice_status(payment.invoice_id))
        except MonoError as error:
            logger.warning("Mono status for invoice %s failed: %s", payment.invoice_id, error)
    return payment
