import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from adify_api.accounts.models import AccountRole
from adify_api.listings.models import Listing, ListingAttachment, ListingCategory, ListingType

Amount = Annotated[Decimal, Field(gt=0, le=Decimal("99999999.99"), decimal_places=2)]
DeliveryDays = Annotated[int, Field(ge=1, le=365)]
Stripped = StringConstraints(strip_whitespace=True)


class Spec(BaseModel):
    """One line of the placement specification, e.g. "Dimensions" / "728 x 90 px"."""

    model_config = ConfigDict(extra="forbid")

    label: Annotated[str, Stripped, Field(min_length=1, max_length=60)]
    value: Annotated[str, Stripped, Field(min_length=1, max_length=300)]


class _ListingCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: ListingCategory
    title: Annotated[str, Stripped, Field(min_length=5, max_length=120)]
    description: Annotated[str, Stripped, Field(min_length=20, max_length=5000)]
    specs: Annotated[list[Spec], Field(max_length=10)] = []


class RequestCreate(_ListingCreate):
    budget_uah: Amount
    delivery_days: DeliveryDays | None = None


class OfferCreate(_ListingCreate):
    price_uah: Amount
    delivery_days: DeliveryDays


class OwnerResponse(BaseModel):
    """The public face of a listing owner: never an email address or phone number."""

    id: uuid.UUID
    display_name: str
    role: AccountRole


class AttachmentResponse(BaseModel):
    id: uuid.UUID
    filename: str
    content_type: str
    size: int
    url: str
    created_at: datetime

    @classmethod
    def from_model(cls, attachment: ListingAttachment) -> "AttachmentResponse":
        return cls(
            id=attachment.id,
            filename=attachment.filename,
            content_type=attachment.content_type,
            size=attachment.size,
            url=f"/api/v1/listings/{attachment.listing_id}/attachments/{attachment.id}",
            created_at=attachment.created_at,
        )


class ListingResponse(BaseModel):
    id: uuid.UUID
    type: ListingType
    category: ListingCategory
    title: str
    description: str
    price_uah: Decimal
    delivery_days: int | None
    specs: list[Spec]
    owner: OwnerResponse
    attachments: list[AttachmentResponse]
    created_at: datetime

    @classmethod
    def from_model(cls, listing: Listing) -> "ListingResponse":
        return cls(
            id=listing.id,
            type=listing.type,
            category=listing.category,
            title=listing.title,
            description=listing.description,
            price_uah=listing.price,
            delivery_days=listing.delivery_days,
            specs=[Spec.model_validate(spec) for spec in listing.specs],
            owner=OwnerResponse(
                id=listing.owner.id,
                display_name=listing.owner.display_name,
                role=listing.owner.role,
            ),
            attachments=[AttachmentResponse.from_model(item) for item in listing.attachments],
            created_at=listing.created_at,
        )


class ListingPage(BaseModel):
    items: list[ListingResponse]
    total: int
