import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from adify_api.accounts.models import Account, _enum
from adify_api.core.config import get_settings
from adify_api.core.db import Base


class ListingType(StrEnum):
    REQUEST = "request"
    OFFER = "offer"


class ListingCategory(StrEnum):
    """The six advertising categories of FR-014."""

    WEBSITE_BANNERS = "website-banners"
    SPONSORED_ARTICLES = "sponsored-articles"
    SOCIAL_MEDIA_POSTS = "social-media-posts"
    VIDEO_INTEGRATIONS = "video-integrations"
    STREAM_ADS = "stream-ads"
    IN_APP_MOBILE_ADS = "in-app-mobile-ads"


class ListingStatus(StrEnum):
    """FR-018/FR-019: derived from ``paused_at`` and ``expires_at``. Expiry wins over a pause."""

    ACTIVE = "active"
    PAUSED = "paused"
    EXPIRED = "expired"


def default_expiry() -> datetime:
    return datetime.now(UTC) + timedelta(days=get_settings().listing_lifetime_days)


class Listing(Base):
    """A customer's ad request or a provider's ad offering; ``price`` is a budget or a price."""

    __tablename__ = "listings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id"), index=True)
    type: Mapped[ListingType] = mapped_column(_enum(ListingType, "listing_type"))
    category: Mapped[ListingCategory] = mapped_column(_enum(ListingCategory, "listing_category"))
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    delivery_days: Mapped[int | None] = mapped_column(Integer)
    specs: Mapped[list[dict[str, str]]] = mapped_column(JSON, default=list)
    # FR-082: optional target audience. Permitted values are still TBD, so they are free text.
    audience_age_min: Mapped[int | None] = mapped_column(Integer)
    audience_age_max: Mapped[int | None] = mapped_column(Integer)
    audience_country: Mapped[str | None] = mapped_column(String(100))
    audience_socioeconomic: Mapped[str | None] = mapped_column(String(100))
    audience_traits: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # FR-018: set while the owner has paused the listing; FR-019: the end of its lifetime.
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=default_expiry, index=True
    )

    owner: Mapped[Account] = relationship(lazy="selectin")
    attachments: Mapped[list["ListingAttachment"]] = relationship(
        lazy="selectin", order_by="ListingAttachment.created_at", cascade="all, delete-orphan"
    )

    @property
    def status(self) -> ListingStatus:
        # SQLite returns naive datetimes; every stored time is UTC.
        expires = self.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        if expires <= datetime.now(UTC):
            return ListingStatus.EXPIRED
        return ListingStatus.PAUSED if self.paused_at is not None else ListingStatus.ACTIVE


class ListingAttachment(Base):
    """File metadata; the bytes live in the attachment storage under the same id."""

    __tablename__ = "listing_attachments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    listing_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("listings.id"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    size: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
