import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Any, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)
from pydantic_core import PydanticCustomError

from adify_api.accounts.models import AccountRole
from adify_api.listings.expiry import expiry_date as selected_expiry_date
from adify_api.listings.expiry import today_in_kyiv
from adify_api.listings.models import (
    Listing,
    ListingAttachment,
    ListingCategory,
    ListingStatus,
    ListingType,
)

Amount = Annotated[Decimal, Field(gt=0, le=Decimal("99999999.99"), decimal_places=2)]
DeliveryDays = Annotated[int, Field(ge=1, le=365)]
Stripped = StringConstraints(strip_whitespace=True)
Age = Annotated[int, Field(ge=0, le=120)]
Title = Annotated[str, Stripped, Field(min_length=5, max_length=120)]
Description = Annotated[str, Stripped, Field(min_length=20, max_length=5000)]


class ListingSort(StrEnum):
    """FR-086: date created or price/budget. Newest first is the default browse order."""

    NEWEST = "newest"
    OLDEST = "oldest"
    PRICE_ASC = "price_asc"
    PRICE_DESC = "price_desc"


class Audience(BaseModel):
    """FR-082 target audience. Value lists are TBD in SRS v1.2, so country and
    socioeconomic background are free text and traits are a short free-text list.
    """

    model_config = ConfigDict(extra="forbid")

    age_min: Age | None = None
    age_max: Age | None = None
    country: Annotated[str, Stripped, Field(min_length=1, max_length=100)] | None = None
    socioeconomic: Annotated[str, Stripped, Field(min_length=1, max_length=100)] | None = None
    traits: Annotated[
        list[Annotated[str, Stripped, Field(min_length=1, max_length=50)]], Field(max_length=20)
    ] = []

    @model_validator(mode="after")
    def ordered_ages(self) -> Self:
        if self.age_min is not None and self.age_max is not None:
            if self.age_min > self.age_max:
                raise ValueError("The minimum age cannot be greater than the maximum age.")
        return self

    def is_empty(self) -> bool:
        return (
            self.age_min is None
            and self.age_max is None
            and self.country is None
            and self.socioeconomic is None
            and not self.traits
        )


class Spec(BaseModel):
    """One line of the placement specification, e.g. "Dimensions" / "728 x 90 px"."""

    model_config = ConfigDict(extra="forbid")

    label: Annotated[str, Stripped, Field(min_length=1, max_length=60)]
    value: Annotated[str, Stripped, Field(min_length=1, max_length=300)]


Specs = Annotated[list[Spec], Field(max_length=10)]


class _ListingCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: ListingCategory
    title: Title
    description: Description
    # FR-021: the owner chooses the day; the listing ends at 23:59 Kyiv time.
    expiry_date: date
    specs: Specs = []
    audience: Audience | None = None

    @field_validator("expiry_date")
    @classmethod
    def not_in_the_past(cls, value: date) -> date:
        if value < today_in_kyiv():
            raise PydanticCustomError(
                "expiry_date_passed", "Choose an expiry date that has not passed."
            )
        return value


class RequestCreate(_ListingCreate):
    budget_uah: Amount
    delivery_days: DeliveryDays | None = None


class OfferCreate(_ListingCreate):
    price_uah: Amount
    delivery_days: DeliveryDays


class ListingUpdate(BaseModel):
    """FR-017: a partial update by the owner. Omitted fields keep their current value.

    ``null`` clears the optional fields: an ad request's delivery time and the target
    audience. ``specs`` and ``audience`` replace the stored values as a whole. A
    request's amount is ``budget_uah``; an offering's is ``price_uah``.
    """

    model_config = ConfigDict(extra="forbid")

    category: ListingCategory | None = None
    title: Title | None = None
    description: Description | None = None
    expiry_date: date | None = None
    budget_uah: Amount | None = None
    price_uah: Amount | None = None
    delivery_days: DeliveryDays | None = None
    specs: Specs | None = None
    audience: Audience | None = None

    @field_validator(
        "category",
        "title",
        "description",
        "expiry_date",
        "budget_uah",
        "price_uah",
        "specs",
        mode="before",
    )
    @classmethod
    def required_when_sent(cls, value: Any) -> Any:
        if value is None:
            raise PydanticCustomError("null_not_allowed", "This field cannot be empty.")
        return value


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
    audience: Audience | None
    owner: OwnerResponse
    attachments: list[AttachmentResponse]
    created_at: datetime
    # FR-018/FR-019: only an active listing takes new orders.
    status: ListingStatus
    # FR-021: 23:59 Kyiv time on this owner-selected date.
    expiry_date: date
    expires_at: datetime

    @classmethod
    def from_model(cls, listing: Listing, **extra: Any) -> Self:
        return cls(
            id=listing.id,
            type=listing.type,
            category=listing.category,
            title=listing.title,
            description=listing.description,
            price_uah=listing.price,
            delivery_days=listing.delivery_days,
            specs=[Spec.model_validate(spec) for spec in listing.specs],
            audience=_audience_from_model(listing),
            owner=OwnerResponse(
                id=listing.owner.id,
                display_name=listing.owner.display_name,
                role=listing.owner.role,
            ),
            attachments=[AttachmentResponse.from_model(item) for item in listing.attachments],
            created_at=listing.created_at,
            status=listing.status,
            expiry_date=selected_expiry_date(listing.expires_at),
            expires_at=listing.expires_at,
            **extra,
        )


class OwnListingResponse(ListingResponse):
    """The owner's view of a listing, with the fields that cannot be changed right now.

    FR-017: ``category`` is locked while the listing has an active order.
    """

    locked_fields: list[str]


def _audience_from_model(listing: Listing) -> Audience | None:
    audience = Audience(
        age_min=listing.audience_age_min,
        age_max=listing.audience_age_max,
        country=listing.audience_country,
        socioeconomic=listing.audience_socioeconomic,
        traits=listing.audience_traits or [],
    )
    return None if audience.is_empty() else audience


class ListingPage(BaseModel):
    items: list[ListingResponse]
    total: int


class PhoneReveal(BaseModel):
    phone: str


class ListingDeletion(BaseModel):
    """FR-020: ``removed`` when the listing is gone; ``soft_deleted`` when order history
    keeps it."""

    result: Literal["removed", "soft_deleted"]
