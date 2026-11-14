"""FR-040, FR-042–FR-044 (ADY-023): review of submitted work.

The provider submits an order in progress for review. The customer accepts it (done) or
requests changes; the provider agrees (back in progress) or declines (it stays in review,
and the customer can accept, ask again, or later open a dispute). The parties agree how
many rounds there are, so the number of requests is not limited.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from adify_api.accounts.models import Account
from adify_api.orders.models import ChangeRequest, ChangeRequestStatus, Order, OrderStatus
from adify_api.orders.service import OrderError


def pending_change_request(order: Order) -> ChangeRequest | None:
    return next((r for r in order.change_requests if r.status == ChangeRequestStatus.PENDING), None)


async def _lock(session: AsyncSession, order: Order, expected: OrderStatus, msg: str) -> None:
    # Both participants act on the same order; the row lock serializes their clicks.
    await session.refresh(order, with_for_update=True)
    if order.status != expected:
        raise OrderError(409, f"order_not_{expected.value}", msg)


def _provider_only(order: Order, account: Account, action: str) -> None:
    if account.id != order.provider_id:
        raise OrderError(403, "not_order_provider", f"Only the provider can {action}.")


def _customer_only(order: Order, account: Account, action: str) -> None:
    if account.id != order.customer_id:
        raise OrderError(403, "not_order_customer", f"Only the customer can {action}.")


async def submit_for_review(session: AsyncSession, order: Order, account: Account) -> Order:
    """FR-040: the provider hands the work to the customer."""
    _provider_only(order, account, "submit the work")
    await _lock(session, order, OrderStatus.IN_PROGRESS, "Only work in progress can be submitted.")
    order.status = OrderStatus.IN_REVIEW
    order.review_started_at = datetime.now(UTC)
    await session.commit()
    return order


async def accept_work(session: AsyncSession, order: Order, account: Account) -> Order:
    """FR-043: the customer accepts the submitted work and the order is done."""
    _customer_only(order, account, "accept the work")
    await _lock(session, order, OrderStatus.IN_REVIEW, "Only submitted work can be accepted.")
    now = datetime.now(UTC)
    if pending := pending_change_request(order):
        pending.status = ChangeRequestStatus.WITHDRAWN
        pending.answered_at = now
    order.status = OrderStatus.DONE
    order.completed_at = now
    await session.commit()
    return order


async def request_changes(
    session: AsyncSession, order: Order, account: Account, message: str
) -> Order:
    """FR-042: the customer explains what to change; the provider answers it."""
    _customer_only(order, account, "request changes")
    await _lock(session, order, OrderStatus.IN_REVIEW, "Changes can be requested only in review.")
    if pending_change_request(order):
        raise OrderError(
            409,
            "change_request_pending",
            "The provider has not answered your last change request yet.",
        )
    order.change_requests.append(
        ChangeRequest(
            message=message, status=ChangeRequestStatus.PENDING, created_at=datetime.now(UTC)
        )
    )
    await session.commit()
    return order


async def answer_change_request(
    session: AsyncSession,
    order: Order,
    account: Account,
    request_id: uuid.UUID,
    *,
    agree: bool,
) -> Order:
    """FR-044: the provider agrees to make the changes or declines them."""
    _provider_only(order, account, "answer a change request")
    await _lock(session, order, OrderStatus.IN_REVIEW, "This order is not in review.")
    request = next((r for r in order.change_requests if r.id == request_id), None)
    if request is None:
        raise OrderError(404, "change_request_not_found", "This change request does not exist.")
    if request.status != ChangeRequestStatus.PENDING:
        raise OrderError(409, "change_request_answered", "This change request is already closed.")
    request.answered_at = datetime.now(UTC)
    if agree:
        request.status = ChangeRequestStatus.AGREED
        order.status = OrderStatus.IN_PROGRESS
        order.review_started_at = None
    else:
        request.status = ChangeRequestStatus.DECLINED
    await session.commit()
    return order
