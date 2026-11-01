import re
import uuid
from decimal import Decimal

from sqlalchemy import String, cast, func, or_, select
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
from adify_api.listings.schemas import ListingSort, OfferCreate, RequestCreate

CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f]")
LIKE_ESCAPE = "\\"


def _like_pattern(text: str) -> str:
    """Escape LIKE wildcards so user input is matched literally (FR-016)."""
    escaped = text.replace(LIKE_ESCAPE, LIKE_ESCAPE * 2)
    escaped = escaped.replace("%", f"{LIKE_ESCAPE}%").replace("_", f"{LIKE_ESCAPE}_")
    return f"%{escaped}%"


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
        audience_age_min=data.audience.age_min if data.audience else None,
        audience_age_max=data.audience.age_max if data.audience else None,
        audience_country=data.audience.country if data.audience else None,
        audience_socioeconomic=data.audience.socioeconomic if data.audience else None,
        audience_traits=data.audience.traits if data.audience else [],
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
    search: str | None = None,
    price_min: Decimal | None = None,
    price_max: Decimal | None = None,
    delivery_max: int | None = None,
    age_min: int | None = None,
    age_max: int | None = None,
    country: str | None = None,
    socioeconomic: str | None = None,
    traits: list[str] | None = None,
    sort: ListingSort = ListingSort.NEWEST,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[Listing], int]:
    """Search and filter public listings (FR-016, FR-084–FR-086).

    ``search`` matches title, description, or category. ``owner_id`` narrows the
    list to one account's own listings. Audience ranges overlap rather than require
    exact equality: asking for ages 18–24 includes a listing targeting 18–34.
    """
    filters = []
    if type_ is not None:
        filters.append(Listing.type == type_)
    if category is not None:
        filters.append(Listing.category == category)
    if owner_id is not None:
        filters.append(Listing.owner_id == owner_id)
    if search and (term := search.strip()):
        pattern = _like_pattern(term)
        filters.append(
            or_(
                Listing.title.ilike(pattern, escape=LIKE_ESCAPE),
                Listing.description.ilike(pattern, escape=LIKE_ESCAPE),
                cast(Listing.category, String).ilike(pattern, escape=LIKE_ESCAPE),
            )
        )
    if price_min is not None:
        filters.append(Listing.price >= price_min)
    if price_max is not None:
        filters.append(Listing.price <= price_max)
    if delivery_max is not None:
        filters.append(Listing.delivery_days <= delivery_max)
    if age_min is not None:
        # A missing maximum is open-ended; a missing minimum is open at the low end.
        filters.append(or_(Listing.audience_age_max.is_(None), Listing.audience_age_max >= age_min))
    if age_max is not None:
        filters.append(or_(Listing.audience_age_min.is_(None), Listing.audience_age_min <= age_max))
    # A listing that declares no audience is open to everyone, so it matches any
    # audience filter. Declared values must match; an absent one stays open-ended.
    for column, value in (
        (Listing.audience_country, country),
        (Listing.audience_socioeconomic, socioeconomic),
    ):
        if value and (term := value.strip()):
            filters.append(
                or_(
                    column.is_(None),
                    cast(column, String).ilike(_like_pattern(term), escape=LIKE_ESCAPE),
                )
            )
    if terms := [trait.strip() for trait in traits or [] if trait.strip()]:
        filters.append(
            or_(
                cast(Listing.audience_traits, String).in_(("[]", "null")),
                *[
                    cast(Listing.audience_traits, String).ilike(
                        _like_pattern(trait), escape=LIKE_ESCAPE
                    )
                    for trait in terms
                ],
            )
        )
    total = await session.scalar(select(func.count()).select_from(Listing).where(*filters))
    # Keep paging stable when many listings share a timestamp or price.
    order = {
        ListingSort.NEWEST: (Listing.created_at.desc(), Listing.id),
        ListingSort.OLDEST: (Listing.created_at.asc(), Listing.id),
        ListingSort.PRICE_ASC: (Listing.price.asc(), Listing.created_at.desc(), Listing.id),
        ListingSort.PRICE_DESC: (Listing.price.desc(), Listing.created_at.desc(), Listing.id),
    }[sort]
    listings = await session.scalars(
        select(Listing).where(*filters).order_by(*order).limit(limit).offset(offset)
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
