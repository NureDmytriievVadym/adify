import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from adify_api.accounts.models import Account
from adify_api.listings.models import ListingCategory, ListingType
from adify_api.listings.schemas import Amount, OwnerResponse, Spec
from adify_api.orders.models import Order, OrderStatus

Details = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
StageTitle = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class StageInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: StageTitle
    deadline: date | None = None


class OrderCreate(BaseModel):
    """FR-033, FR-037: the agreement the listing owner records in the chat."""

    model_config = ConfigDict(extra="forbid")

    details: Details
    price_uah: Amount
    deadline: date | None = None
    stages: Annotated[list[StageInput], Field(max_length=10)] = []

    @model_validator(mode="after")
    def deadlines_ahead(self) -> "OrderCreate":
        today = datetime.now(UTC).date()
        if self.deadline is not None and self.deadline < today:
            raise ValueError("The order deadline cannot be in the past.")
        for stage in self.stages:
            if stage.deadline is not None and stage.deadline < today:
                raise ValueError(f"The deadline of “{stage.title}” cannot be in the past.")
            if self.deadline and stage.deadline and stage.deadline > self.deadline:
                raise ValueError(
                    f"The deadline of “{stage.title}” is later than the order deadline."
                )
        return self


class RequirementsSnapshot(BaseModel):
    """FR-118: copied at creation; ``has_requirements`` is false for an ad request without any."""

    listing_type: ListingType
    category: ListingCategory
    has_requirements: bool
    specs: list[Spec]


class StageResponse(BaseModel):
    title: str
    deadline: date | None


class OrderListing(BaseModel):
    id: uuid.UUID
    title: str
    type: ListingType


class OrderResponse(BaseModel):
    """An order for one of its two participants; contacts are never included (FR-087)."""

    id: uuid.UUID
    status: OrderStatus
    details: str
    price_uah: Decimal
    deadline: date | None
    stages: list[StageResponse]
    requirements: RequirementsSnapshot
    listing: OrderListing
    chat_id: uuid.UUID | None
    is_listing_owner: bool
    customer: OwnerResponse
    provider: OwnerResponse
    created_at: datetime

    @classmethod
    def for_viewer(cls, order: Order, viewer: Account) -> "OrderResponse":
        def public(account: Account) -> OwnerResponse:
            return OwnerResponse(
                id=account.id, display_name=account.display_name, role=account.role
            )

        return cls(
            id=order.id,
            status=order.status,
            details=order.details,
            price_uah=order.price,
            deadline=order.deadline,
            stages=[StageResponse(title=s.title, deadline=s.deadline) for s in order.stages],
            requirements=RequirementsSnapshot.model_validate(order.requirements),
            listing=OrderListing(
                id=order.listing.id, title=order.listing.title, type=order.listing.type
            ),
            chat_id=order.chat_id,
            is_listing_owner=order.owner_id == viewer.id,
            customer=public(order.customer),
            provider=public(order.provider),
            created_at=order.created_at,
        )
