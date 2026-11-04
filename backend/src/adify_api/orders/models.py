import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from adify_api.accounts.models import _enum
from adify_api.core.db import Base


class OrderStatus(StrEnum):
    """Order states. The full lifecycle and its transitions belong to the order stories."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    DISPUTED = "disputed"


# An order is active until it is closed. A dispute is still open, so it keeps the order active.
ACTIVE_ORDER_STATUSES = frozenset(
    {OrderStatus.PENDING, OrderStatus.IN_PROGRESS, OrderStatus.DISPUTED}
)


class Order(Base):
    """An order placed on a listing between one customer and one provider.

    Only the columns needed by listing rules (FR-017) exist so far; creating and
    progressing orders arrives with the order stories.
    """

    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    listing_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("listings.id"), index=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id"), index=True)
    provider_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id"), index=True)
    status: Mapped[OrderStatus] = mapped_column(
        _enum(OrderStatus, "order_status"), default=OrderStatus.PENDING
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
