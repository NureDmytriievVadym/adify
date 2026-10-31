import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from adify_api.accounts.models import Account, _enum
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    owner: Mapped[Account] = relationship(lazy="selectin")
    attachments: Mapped[list["ListingAttachment"]] = relationship(
        lazy="selectin", order_by="ListingAttachment.created_at", cascade="all, delete-orphan"
    )


class ListingAttachment(Base):
    """File metadata; the bytes live in the attachment storage under the same id."""

    __tablename__ = "listing_attachments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    listing_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("listings.id"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    size: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
