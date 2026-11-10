import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from adify_api.accounts.models import Account, _enum
from adify_api.core.db import Base
from adify_api.listings.models import Listing


class OrderStatus(StrEnum):
    """Order states from SRS §3.4.4; transitions arrive with their order stories."""

    AWAITING_PAYMENT = "awaiting_payment"
    PAID = "paid"
    IN_PROGRESS = "in_progress"
    IN_REVIEW = "in_review"
    DISPUTED = "disputed"
    DONE = "done"
    CANCELED = "canceled"
    REJECTED = "rejected"


# FR-017: an order is active in any state other than canceled, rejected, or done.
ACTIVE_ORDER_STATUSES = frozenset(OrderStatus) - {
    OrderStatus.DONE,
    OrderStatus.CANCELED,
    OrderStatus.REJECTED,
}


class Order(Base):
    """An order on a listing between its owner and the other chat participant (FR-033, FR-036).

    ``requirements`` is the snapshot of the listing's technical requirements taken at
    creation (FR-118); later listing edits never change it.
    """

    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    listing_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("listings.id"), index=True)
    chat_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("chats.id", ondelete="SET NULL"), index=True
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id"), index=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id"), index=True)
    provider_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id"), index=True)
    status: Mapped[OrderStatus] = mapped_column(
        _enum(OrderStatus, "order_status"), default=OrderStatus.AWAITING_PAYMENT
    )
    details: Mapped[str] = mapped_column(Text, default="")
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    deadline: Mapped[date | None] = mapped_column(Date)
    requirements: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    listing: Mapped[Listing] = relationship(lazy="selectin")
    customer: Mapped[Account] = relationship(foreign_keys=[customer_id], lazy="selectin")
    provider: Mapped[Account] = relationship(foreign_keys=[provider_id], lazy="selectin")
    stages: Mapped[list["OrderStage"]] = relationship(
        lazy="selectin", order_by="OrderStage.position", cascade="all, delete-orphan"
    )


class OrderStage(Base):
    """FR-037: an optional work stage, each with its own optional completion deadline."""

    __tablename__ = "order_stages"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(120))
    deadline: Mapped[date | None] = mapped_column(Date)
