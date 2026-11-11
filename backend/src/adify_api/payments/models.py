import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from adify_api.accounts.models import _enum
from adify_api.core.db import Base


class PaymentStatus(StrEnum):
    """Mono invoice statuses, stored as Mono reports them."""

    CREATED = "created"
    PROCESSING = "processing"
    HOLD = "hold"
    SUCCESS = "success"
    FAILURE = "failure"
    REVERSED = "reversed"
    EXPIRED = "expired"


# Mono may still change these; the others are final for the invoice.
OPEN_PAYMENT_STATUSES = frozenset({PaymentStatus.CREATED, PaymentStatus.PROCESSING})


class Payment(Base):
    """One Mono hold invoice for an order (FR-038). A failed or expired invoice stays as
    history and the customer pays again with a new one."""

    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), index=True
    )
    invoice_id: Mapped[str] = mapped_column(String(64), unique=True)
    page_url: Mapped[str] = mapped_column(String(500))
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    status: Mapped[PaymentStatus] = mapped_column(
        _enum(PaymentStatus, "payment_status"), default=PaymentStatus.CREATED
    )
    failure_reason: Mapped[str | None] = mapped_column(String(500))
    # Mono's modifiedDate of the last applied update; webhooks may arrive out of order.
    provider_modified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
