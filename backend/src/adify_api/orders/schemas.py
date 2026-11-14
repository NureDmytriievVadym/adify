import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)
from pydantic_core import PydanticCustomError

from adify_api.accounts.models import Account
from adify_api.core.config import get_settings
from adify_api.listings.models import ListingCategory, ListingType
from adify_api.listings.schemas import Amount, OwnerResponse, Spec
from adify_api.orders.creatives import work_start_blocker
from adify_api.orders.models import ChangeRequestStatus, Order, OrderStatus

Details = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
ChangeMessage = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)
]


class ChangeRequestCreate(BaseModel):
    """FR-042: what the customer wants changed in the submitted work."""

    model_config = ConfigDict(extra="forbid")

    message: ChangeMessage


class ChangeRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    message: str
    status: ChangeRequestStatus
    created_at: datetime
    answered_at: datetime | None


StageTitle = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class StageInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: StageTitle
    deadline: date | None = None

    @field_validator("deadline")
    @classmethod
    def deadline_not_past(cls, value: date | None) -> date | None:
        if value is not None and value < datetime.now(UTC).date():
            raise PydanticCustomError(
                "stage_deadline_past", "The stage deadline cannot be in the past."
            )
        return value


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
    # FR-124: set by creative validation (ADY-055); older snapshots never ask for creatives.
    requires_creatives: bool = False


def _utc(moment: datetime | None) -> datetime | None:
    # SQLite drops the zone of stored timestamps; every stored time is UTC.
    return moment.replace(tzinfo=UTC) if moment and moment.tzinfo is None else moment


def start_deadline(order: Order) -> datetime | None:
    """FR-132: when a paid order is canceled unless the provider starts work."""
    if order.status != OrderStatus.PAID or order.paid_at is None:
        return None
    return _utc(order.paid_at) + timedelta(days=get_settings().paid_order_start_timeout_days)


class StageResponse(BaseModel):
    id: uuid.UUID
    title: str
    deadline: date | None
    completed_at: datetime | None
    completed_by: OwnerResponse | None


class EvidenceFileResponse(BaseModel):
    id: uuid.UUID
    filename: str
    content_type: str
    size: int
    url: str
    created_at: datetime


class EvidenceResponse(BaseModel):
    id: uuid.UUID
    author: OwnerResponse
    note: str | None
    files: list[EvidenceFileResponse]
    created_at: datetime


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
    paid_at: datetime | None
    # FR-132: a paid order not started by then is canceled and its hold released.
    start_deadline: datetime | None
    work_started_at: datetime | None
    # FR-124: why Start work is unavailable while the order is paid, such as a missing creative.
    work_start_blocker: str | None
    canceled_at: datetime | None
    cancel_reason: str | None
    # FR-040–FR-044: the latest submission, acceptance, and every change request, oldest first.
    review_started_at: datetime | None
    completed_at: datetime | None
    change_requests: list[ChangeRequestResponse]
    # FR-041: evidence from both participants, oldest first.
    evidence: list[EvidenceResponse]

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
            stages=[
                StageResponse(
                    id=s.id,
                    title=s.title,
                    deadline=s.deadline,
                    completed_at=s.completed_at,
                    completed_by=public(s.completed_by) if s.completed_by else None,
                )
                for s in order.stages
            ],
            requirements=RequirementsSnapshot.model_validate(order.requirements),
            listing=OrderListing(
                id=order.listing.id, title=order.listing.title, type=order.listing.type
            ),
            chat_id=order.chat_id,
            is_listing_owner=order.owner_id == viewer.id,
            customer=public(order.customer),
            provider=public(order.provider),
            created_at=order.created_at,
            paid_at=order.paid_at,
            start_deadline=start_deadline(order),
            work_started_at=order.work_started_at,
            work_start_blocker=(
                work_start_blocker(order) if order.status == OrderStatus.PAID else None
            ),
            canceled_at=order.canceled_at,
            cancel_reason=order.cancel_reason,
            review_started_at=order.review_started_at,
            completed_at=order.completed_at,
            change_requests=[
                ChangeRequestResponse.model_validate(r) for r in order.change_requests
            ],
            evidence=[
                EvidenceResponse(
                    id=e.id,
                    author=public(e.author),
                    note=e.note,
                    files=[
                        EvidenceFileResponse(
                            id=f.id,
                            filename=f.filename,
                            content_type=f.content_type,
                            size=f.size,
                            url=f"/api/v1/orders/{order.id}/evidence/{e.id}/files/{f.id}",
                            created_at=f.created_at,
                        )
                        for f in e.files
                    ],
                    created_at=e.created_at,
                )
                for e in order.evidence
            ],
        )
