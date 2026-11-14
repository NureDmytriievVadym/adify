"""Order transitions that move money through Mono: Start work and the start timeout."""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from adify_api.accounts.models import Account
from adify_api.core.config import get_settings
from adify_api.orders.creatives import work_start_blocker
from adify_api.orders.models import CancelReason, Order, OrderStatus
from adify_api.orders.service import OrderError
from adify_api.payments.models import Payment, PaymentStatus
from adify_api.payments.mono import MonoClient, MonoError

logger = logging.getLogger(__name__)


async def _held_payment(session: AsyncSession, order: Order) -> Payment | None:
    """The invoice holding (or, after a retry, already charging) the order's funds."""
    return await session.scalar(
        select(Payment)
        .where(
            Payment.order_id == order.id,
            Payment.status.in_([PaymentStatus.HOLD, PaymentStatus.SUCCESS]),
        )
        .order_by(Payment.created_at.desc(), Payment.id)
        .limit(1)
    )


async def start_work(
    session: AsyncSession, order: Order, account: Account, mono: MonoClient | None
) -> Order:
    """FR-039, FR-056: the provider starts a paid order and Mono charges the held funds.

    The order moves to in progress only after Mono finalizes the hold, so a failure at
    Mono leaves it paid and the provider can try again.
    """
    if account.id != order.provider_id:
        raise OrderError(403, "not_order_provider", "Only the provider can start work.")
    # Two clicks at once must not finalize twice; the second waits and then sees the change.
    await session.refresh(order, with_for_update=True)
    if order.status != OrderStatus.PAID:
        raise OrderError(409, "order_not_paid", "Work can start only on a paid order.")
    if blocker := work_start_blocker(order):
        raise OrderError(409, "no_validated_creative", f"{blocker}: the customer must attach one.")
    if mono is None:
        raise OrderError(
            503, "payments_unavailable", "Payments are not available right now. Try again later."
        )
    payment = await _held_payment(session, order)
    if payment is None:
        raise OrderError(409, "hold_not_found", "Mono holds no funds for this order.")
    if payment.status == PaymentStatus.HOLD:
        try:
            await mono.finalize_hold(payment.invoice_id, payment.amount)
        except MonoError as error:
            logger.error("Finalizing invoice %s failed: %s", payment.invoice_id, error)
            raise OrderError(
                502, "payment_provider_error", "Mono could not charge the payment. Try again."
            ) from None
        payment.status = PaymentStatus.SUCCESS
    order.status = OrderStatus.IN_PROGRESS
    order.work_started_at = datetime.now(UTC)
    await session.commit()
    return order


async def cancel_unstarted_orders(
    session: AsyncSession, mono: MonoClient, now: datetime | None = None
) -> list[Order]:
    """FR-132: cancel paid orders not started within the timeout and release their holds.

    An order whose hold Mono does not release is left paid, logged, and retried on the
    next run; Mono itself cancels a hold after 9 days.
    """
    now = now or datetime.now(UTC)
    cutoff = now - timedelta(days=get_settings().paid_order_start_timeout_days)
    due = await session.scalars(
        select(Order)
        .where(Order.status == OrderStatus.PAID, Order.paid_at <= cutoff)
        .order_by(Order.paid_at, Order.id)
    )
    canceled = []
    for order in list(due):
        payment = await _held_payment(session, order)
        # A charge left by an interrupted Start work is refunded the same way.
        if payment is not None:
            try:
                await mono.cancel_invoice(payment.invoice_id)
            except MonoError as error:
                logger.error("Releasing the hold of order %s failed: %s", order.id, error)
                continue
            payment.status = PaymentStatus.REVERSED
        order.status = OrderStatus.CANCELED
        order.canceled_at = now
        order.cancel_reason = CancelReason.START_TIMEOUT
        await session.commit()
        logger.info("Canceled order %s: work did not start in time", order.id)
        canceled.append(order)
    return canceled
