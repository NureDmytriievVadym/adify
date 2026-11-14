"""Order transitions that move money through Mono: Start work, canceling or rejecting an
order before work starts, and the start timeout."""

import logging
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from adify_api.accounts.models import Account
from adify_api.core.config import get_settings
from adify_api.orders.creatives import work_start_blocker
from adify_api.orders.models import CancelReason, Order, OrderStatus
from adify_api.orders.service import OrderError
from adify_api.payments.models import OPEN_PAYMENT_STATUSES, Payment, PaymentStatus
from adify_api.payments.mono import MonoClient, MonoError

logger = logging.getLogger(__name__)

# FR-046, FR-047: before work starts either participant can end the order.
ENDABLE_STATUSES = frozenset({OrderStatus.AWAITING_PAYMENT, OrderStatus.PAID})
ENDED_STATUSES = frozenset({OrderStatus.CANCELED, OrderStatus.REJECTED})
# Held, or charged by a Start work that did not finish.
MONEY_AT_MONO = (PaymentStatus.HOLD, PaymentStatus.SUCCESS)


def _payments_unavailable() -> OrderError:
    return OrderError(
        503, "payments_unavailable", "Payments are not available right now. Try again later."
    )


async def _payments(
    session: AsyncSession, order: Order, statuses: Iterable[PaymentStatus]
) -> list[Payment]:
    return list(
        await session.scalars(
            select(Payment)
            .where(Payment.order_id == order.id, Payment.status.in_(statuses))
            .order_by(Payment.created_at.desc(), Payment.id)
        )
    )


async def _held_payment(session: AsyncSession, order: Order) -> Payment | None:
    """The invoice holding (or, after a retry, already charging) the order's funds."""
    held = await _payments(session, order, MONEY_AT_MONO)
    return held[0] if held else None


async def _release_funds(session: AsyncSession, order: Order, mono: MonoClient) -> None:
    """FR-096: leave nothing at Mono for an order that ends before work starts.

    An unpaid invoice is invalidated, so its payment page can no longer take money, and a
    hold is released (a charge left by an interrupted Start work is refunded the same way).
    Raises ``MonoError`` and changes nothing it has not finished when Mono refuses.
    """
    for payment in await _payments(session, order, OPEN_PAYMENT_STATUSES):
        await mono.remove_invoice(payment.invoice_id)
        payment.status = PaymentStatus.EXPIRED
        payment.failure_reason = "Removed when the order ended"
    if (payment := await _held_payment(session, order)) is not None:
        await mono.cancel_invoice(payment.invoice_id)
        payment.status = PaymentStatus.REVERSED


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
        raise _payments_unavailable()
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


async def _end_before_work(
    session: AsyncSession,
    order: Order,
    mono: MonoClient | None,
    *,
    status: OrderStatus,
    reason: CancelReason,
    verb: str,
) -> Order:
    await session.refresh(order, with_for_update=True)
    # After Start work the order can never be canceled or rejected, even if a price change
    # (ADY-024) brings it back to awaiting payment; a dispute is the way out then.
    if order.work_started_at is not None:
        raise OrderError(
            409,
            "work_started",
            f"Work has started, so the order can no longer be {verb}. Open a dispute instead.",
        )
    if order.status not in ENDABLE_STATUSES:
        raise OrderError(409, "order_not_endable", f"This order can no longer be {verb}.")
    if await _payments(session, order, [*OPEN_PAYMENT_STATUSES, *MONEY_AT_MONO]):
        if mono is None:
            raise _payments_unavailable()
        try:
            await _release_funds(session, order, mono)
        except MonoError as error:
            await session.commit()  # keep what Mono already did; the order is unchanged
            logger.error("Releasing the funds of order %s failed: %s", order.id, error)
            raise OrderError(
                502, "payment_provider_error", "Mono could not release the payment. Try again."
            ) from None
    order.status = status
    order.canceled_at = datetime.now(UTC)
    order.cancel_reason = reason
    await session.commit()
    return order


async def cancel_order(
    session: AsyncSession, order: Order, account: Account, mono: MonoClient | None
) -> Order:
    """FR-046 (ADY-025): the customer cancels an order awaiting payment or paid."""
    if account.id != order.customer_id:
        raise OrderError(403, "not_order_customer", "Only the customer can cancel an order.")
    return await _end_before_work(
        session,
        order,
        mono,
        status=OrderStatus.CANCELED,
        reason=CancelReason.CUSTOMER_CANCELED,
        verb="canceled",
    )


async def reject_order(
    session: AsyncSession, order: Order, account: Account, mono: MonoClient | None
) -> Order:
    """FR-047 (ADY-026): the provider rejects an order awaiting payment or paid."""
    if account.id != order.provider_id:
        raise OrderError(403, "not_order_provider", "Only the provider can reject an order.")
    return await _end_before_work(
        session,
        order,
        mono,
        status=OrderStatus.REJECTED,
        reason=CancelReason.PROVIDER_REJECTED,
        verb="rejected",
    )


async def release_stray_hold(session: AsyncSession, payment: Payment, mono: MonoClient) -> None:
    """A hold that arrives for an order already canceled or rejected is released at once.

    Mono may report a payment made just before its invoice was removed.
    """
    if payment.status != PaymentStatus.HOLD:
        return
    order = await session.get(Order, payment.order_id)
    if order is None or order.status not in ENDED_STATUSES:
        return
    logger.warning("Order %s ended before its payment arrived; releasing the hold", order.id)
    try:
        await mono.cancel_invoice(payment.invoice_id)
    except MonoError as error:
        logger.error("Releasing the stray hold %s failed: %s", payment.invoice_id, error)
        return
    payment.status = PaymentStatus.REVERSED
    await session.commit()


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
        try:
            await _release_funds(session, order, mono)
        except MonoError as error:
            await session.commit()  # keep what Mono already did; the order is unchanged
            logger.error("Releasing the hold of order %s failed: %s", order.id, error)
            continue
        order.status = OrderStatus.CANCELED
        order.canceled_at = now
        order.cancel_reason = CancelReason.START_TIMEOUT
        await session.commit()
        logger.info("Canceled order %s: work did not start in time", order.id)
        canceled.append(order)
    return canceled
