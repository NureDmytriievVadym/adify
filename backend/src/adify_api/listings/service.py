import re
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from adify_api.accounts.models import Account
from adify_api.core.config import get_settings
from adify_api.listings import storage
from adify_api.listings.models import (
    Listing,
    ListingAttachment,
    ListingCategory,
    ListingType,
)
from adify_api.listings.schemas import OfferCreate, RequestCreate

CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f]")


class ListingError(Exception):
    def __init__(self, status_code: int, type_: str, msg: str) -> None:
        super().__init__(type_)
        self.status_code = status_code
        self.type = type_
        self.msg = msg


async def create_request(session: AsyncSession, owner: Account, data: RequestCreate) -> Listing:
    return await _create(
        session, owner, ListingType.REQUEST, data, data.budget_uah, data.delivery_days
    )


async def create_offer(session: AsyncSession, owner: Account, data: OfferCreate) -> Listing:
    return await _create(
        session, owner, ListingType.OFFER, data, data.price_uah, data.delivery_days
    )


async def _create(session, owner, type_, data, price, delivery_days) -> Listing:
    listing = Listing(
        owner_id=owner.id,
        type=type_,
        category=data.category,
        title=data.title,
        description=data.description,
        price=price,
        delivery_days=delivery_days,
        specs=[spec.model_dump() for spec in data.specs],
    )
    session.add(listing)
    await session.commit()
    await session.refresh(listing)
    return listing


async def list_listings(
    session: AsyncSession,
    *,
    type_: ListingType | None = None,
    category: ListingCategory | None = None,
    owner_id: uuid.UUID | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[Listing], int]:
    """Newest first; ``owner_id`` narrows the list to one account's own listings."""
    filters = []
    if type_ is not None:
        filters.append(Listing.type == type_)
    if category is not None:
        filters.append(Listing.category == category)
    if owner_id is not None:
        filters.append(Listing.owner_id == owner_id)
    total = await session.scalar(select(func.count()).select_from(Listing).where(*filters))
    listings = await session.scalars(
        select(Listing)
        .where(*filters)
        .order_by(Listing.created_at.desc(), Listing.id)
        .limit(limit)
        .offset(offset)
    )
    return list(listings), total or 0


async def get_listing(session: AsyncSession, listing_id: uuid.UUID) -> Listing:
    listing = await session.get(Listing, listing_id)
    if listing is None:
        raise ListingError(404, "listing_not_found", "This listing could not be found.")
    return listing


def ensure_owner(listing: Listing, account: Account) -> None:
    if listing.owner_id != account.id:
        raise ListingError(403, "not_listing_owner", "Only the owner can change this listing.")


def clean_filename(filename: str) -> str:
    name = CONTROL_CHARACTERS.sub("", filename.replace("\\", "/").rsplit("/", 1)[-1]).strip()
    return name[-255:] or "attachment"


async def add_attachment(
    session: AsyncSession, listing: Listing, filename: str, data: bytes
) -> ListingAttachment:
    settings = get_settings()
    if not data:
        raise ListingError(422, "attachment_empty", "The file is empty.")
    content_type = storage.sniff_content_type(data)
    if content_type is None:
        raise ListingError(
            415,
            "attachment_type_not_allowed",
            "Attach a JPG, PNG, GIF, WebP, MP4, or PDF file.",
        )
    if len(listing.attachments) >= settings.max_attachments:
        raise ListingError(
            409,
            "too_many_attachments",
            f"A listing can have at most {settings.max_attachments} attachments.",
        )
    attachment = ListingAttachment(
        id=uuid.uuid4(),
        listing_id=listing.id,
        filename=clean_filename(filename),
        content_type=content_type,
        size=len(data),
    )
    await storage.save(attachment.id, data)
    session.add(attachment)
    try:
        await session.commit()
    except Exception:
        await storage.remove(attachment.id)
        raise
    await session.refresh(listing)
    return attachment


async def delete_attachment(
    session: AsyncSession, listing: Listing, attachment_id: uuid.UUID
) -> None:
    attachment = next((item for item in listing.attachments if item.id == attachment_id), None)
    if attachment is None:
        raise ListingError(404, "attachment_not_found", "This attachment could not be found.")
    listing.attachments.remove(attachment)
    await session.commit()
    await storage.remove(attachment_id)
