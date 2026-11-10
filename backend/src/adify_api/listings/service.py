import re
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import String, cast, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from adify_api.accounts.models import Account
from adify_api.core.config import get_settings
from adify_api.listings import storage
from adify_api.listings.models import (
    Listing,
    ListingAttachment,
    ListingCategory,
    ListingStatus,
    ListingType,
)
from adify_api.listings.schemas import (
    Audience,
    ListingSort,
    ListingUpdate,
    OfferCreate,
    RequestCreate,
)
from adify_api.orders.models import ACTIVE_ORDER_STATUSES, Order

CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f]")
LIKE_ESCAPE = "\\"


def _like_pattern(text: str) -> str:
    """Escape LIKE wildcards so user input is matched literally (FR-016)."""
    escaped = text.replace(LIKE_ESCAPE, LIKE_ESCAPE * 2)
    escaped = escaped.replace("%", f"{LIKE_ESCAPE}%").replace("_", f"{LIKE_ESCAPE}_")
    return f"%{escaped}%"


class ListingError(Exception):
    def __init__(self, status_code: int, type_: str, msg: str, field: str | None = None) -> None:
        super().__init__(type_)
        self.status_code = status_code
        self.type = type_
        self.msg = msg
        self.field = field


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
    _set_audience(listing, data.audience)
    session.add(listing)
    await session.commit()
    await session.refresh(listing)
    return listing


def _set_audience(listing: Listing, audience: Audience | None) -> None:
    listing.audience_age_min = audience.age_min if audience else None
    listing.audience_age_max = audience.age_max if audience else None
    listing.audience_country = audience.country if audience else None
    listing.audience_socioeconomic = audience.socioeconomic if audience else None
    listing.audience_traits = list(audience.traits) if audience else []


async def has_active_order(session: AsyncSession, listing_id: uuid.UUID) -> bool:
    return bool(
        await session.scalar(
            select(
                exists().where(
                    Order.listing_id == listing_id, Order.status.in_(ACTIVE_ORDER_STATUSES)
                )
            )
        )
    )


async def has_order_history(session: AsyncSession, listing_id: uuid.UUID) -> bool:
    return bool(await session.scalar(select(exists().where(Order.listing_id == listing_id))))


async def locked_fields(session: AsyncSession, listing: Listing) -> list[str]:
    """FR-017: what the owner cannot change right now. The category is fixed while an
    order is active, because the order was agreed for that kind of placement."""
    return ["category"] if await has_active_order(session, listing.id) else []


async def update_listing(session: AsyncSession, listing: Listing, data: ListingUpdate) -> Listing:
    """Apply an owner's partial update (FR-017). Nothing is saved if any rule fails."""
    ensure_not_deleted(listing)
    sent = data.model_fields_set
    is_request = listing.type == ListingType.REQUEST
    wrong_amount = "price_uah" if is_request else "budget_uah"
    if wrong_amount in sent:
        raise ListingError(
            422,
            "amount_field_mismatch",
            "Ad requests have a budget_uah; ad offerings have a price_uah.",
            wrong_amount,
        )
    if "delivery_days" in sent and data.delivery_days is None and not is_request:
        raise ListingError(
            422, "delivery_required", "An ad offering needs a delivery time.", "delivery_days"
        )
    if "category" in sent and data.category != listing.category:
        if await has_active_order(session, listing.id):
            raise ListingError(
                409,
                "category_locked",
                "The category cannot be changed while this listing has an active order.",
                "category",
            )
        listing.category = data.category

    for field in ("title", "description", "delivery_days"):
        if field in sent:
            setattr(listing, field, getattr(data, field))
    amount = data.budget_uah if is_request else data.price_uah
    if amount is not None:
        listing.price = amount
    if data.specs is not None:
        listing.specs = [spec.model_dump() for spec in data.specs]
    if "audience" in sent:
        _set_audience(
            listing, None if data.audience is None or data.audience.is_empty() else data.audience
        )
    await session.commit()
    await session.refresh(listing)
    return listing


async def list_listings(
    session: AsyncSession,
    *,
    type_: ListingType | None = None,
    category: ListingCategory | None = None,
    owner_id: uuid.UUID | None = None,
    open_only: bool = False,
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
    list to one account's own listings. ``open_only`` keeps only active listings: the
    public marketplace hides paused and expired ones (FR-018, FR-019). Soft-deleted
    listings are left out everywhere, the owner's own list included (FR-020). Audience ranges
    overlap rather than require exact equality: asking for ages 18–24 includes a listing
    targeting 18–34.
    """
    filters = [Listing.deleted_at.is_(None)]
    if type_ is not None:
        filters.append(Listing.type == type_)
    if category is not None:
        filters.append(Listing.category == category)
    if owner_id is not None:
        filters.append(Listing.owner_id == owner_id)
    if open_only:
        filters.append(Listing.paused_at.is_(None))
        filters.append(Listing.expires_at > datetime.now(UTC))
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


def ensure_can_chat(listing: Listing, account: Account) -> None:
    if listing.owner_id == account.id:
        raise ListingError(403, "own_listing", "You cannot start a chat about your own listing.")
    if listing.owner.role == account.role:
        raise ListingError(403, "same_role_chat", "Chats connect one customer and one provider.")


def ensure_accepts_orders(listing: Listing) -> None:
    """FR-018/FR-019: only an active listing takes new orders.

    Chats still start on paused and expired listings (FR-026); order creation, including
    from an existing chat (FR-031), must call this.
    """
    status = listing.status
    if status == ListingStatus.SOFT_DELETED:
        raise ListingError(
            409, "listing_deleted", "This listing was deleted and is not accepting new orders."
        )
    if status == ListingStatus.PAUSED:
        raise ListingError(
            409, "listing_paused", "This listing is paused and is not accepting new orders."
        )
    if status == ListingStatus.EXPIRED:
        raise ListingError(
            409, "listing_expired", "This listing has expired and is not accepting new orders."
        )


async def pause_listing(session: AsyncSession, listing: Listing) -> Listing:
    """FR-018: stop new orders. Existing orders continue; pausing twice is a no-op."""
    ensure_not_deleted(listing)
    if listing.status == ListingStatus.EXPIRED:
        raise ListingError(409, "listing_expired", "This listing has already expired.")
    if listing.paused_at is None:
        listing.paused_at = datetime.now(UTC)
        await session.commit()
        await session.refresh(listing)
    return listing


async def resume_listing(session: AsyncSession, listing: Listing) -> Listing:
    """FR-018/FR-019: take new orders again, unless the listing's lifetime has ended."""
    ensure_not_deleted(listing)
    if listing.status == ListingStatus.EXPIRED:
        raise ListingError(409, "listing_expired", "An expired listing cannot be resumed.")
    if listing.paused_at is not None:
        listing.paused_at = None
        await session.commit()
        await session.refresh(listing)
    return listing


async def delete_listing(session: AsyncSession, listing: Listing) -> ListingStatus | None:
    """FR-020: soft-delete a listing with any order history, remove one without outright.

    Returns ``SOFT_DELETED``, or ``None`` when the listing is gone. Orders keep pointing at a
    soft-deleted listing; chats lose the reference of a removed one (``ON DELETE SET NULL``).
    Deleting a soft-deleted listing again changes nothing.
    """
    if listing.deleted_at is None and not await has_order_history(session, listing.id):
        attachment_ids = [attachment.id for attachment in listing.attachments]
        await session.delete(listing)
        await session.commit()
        for attachment_id in attachment_ids:
            await storage.remove(attachment_id)
        return None
    if listing.deleted_at is None:
        listing.deleted_at = datetime.now(UTC)
        await session.commit()
    return ListingStatus.SOFT_DELETED


def ensure_not_deleted(listing: Listing) -> None:
    """FR-020: a soft-deleted listing is only kept as a record and can no longer change."""
    if listing.deleted_at is not None:
        raise ListingError(409, "listing_deleted", "This listing has been deleted.")


def ensure_owner(listing: Listing, account: Account) -> None:
    if listing.owner_id != account.id:
        raise ListingError(403, "not_listing_owner", "Only the owner can change this listing.")


def clean_filename(filename: str) -> str:
    name = CONTROL_CHARACTERS.sub("", filename.replace("\\", "/").rsplit("/", 1)[-1]).strip()
    return name[-255:] or "attachment"


async def add_attachment(
    session: AsyncSession, listing: Listing, filename: str, data: bytes
) -> ListingAttachment:
    ensure_not_deleted(listing)
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
    ensure_not_deleted(listing)
    attachment = next((item for item in listing.attachments if item.id == attachment_id), None)
    if attachment is None:
        raise ListingError(404, "attachment_not_found", "This attachment could not be found.")
    listing.attachments.remove(attachment)
    await session.commit()
    await storage.remove(attachment_id)
