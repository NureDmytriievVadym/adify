import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from adify_api.accounts.models import Account
from adify_api.core.db import Base
from adify_api.listings.models import Listing


class Chat(Base):
    """One conversation per listing and pair of participants; starting it again reuses it."""

    __tablename__ = "chats"
    __table_args__ = (UniqueConstraint("listing_id", "customer_id", "provider_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # A permanently deleted listing leaves its chats in place without the reference (SRS §3.4.3).
    listing_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("listings.id", ondelete="SET NULL"), index=True
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id"), index=True)
    provider_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    listing: Mapped[Listing | None] = relationship(lazy="selectin")
    customer: Mapped[Account] = relationship(foreign_keys=[customer_id], lazy="selectin")
    provider: Mapped[Account] = relationship(foreign_keys=[provider_id], lazy="selectin")
