from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from adify_api.accounts.models import Account
from adify_api.orders.models import Order
from adify_api.payments.models import OPEN_PAYMENT_STATUSES, Payment, PaymentStatus


class PaymentResponse(BaseModel):
    """An order's latest Mono payment. ``page_url`` is only for the customer while it is open."""

    status: PaymentStatus
    amount_uah: Decimal
    page_url: str | None
    failure_reason: str | None
    created_at: datetime

    @classmethod
    def for_viewer(cls, payment: Payment, order: Order, viewer: Account) -> "PaymentResponse":
        payable = viewer.id == order.customer_id and payment.status in OPEN_PAYMENT_STATUSES
        return cls(
            status=payment.status,
            amount_uah=payment.amount,
            page_url=payment.page_url if payable else None,
            failure_reason=payment.failure_reason,
            created_at=payment.created_at,
        )
