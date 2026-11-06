import uuid
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from adify_api.accounts.models import AccountRole
from adify_api.accounts.schemas import ErrorResponse
from adify_api.auth.dependencies import CurrentAccount, VerifiedAccount
from adify_api.chats import service as chats_service
from adify_api.chats.schemas import ChatResponse
from adify_api.core.config import get_settings
from adify_api.core.db import get_session
from adify_api.listings import service, storage
from adify_api.listings.models import Listing, ListingCategory, ListingType
from adify_api.listings.schemas import (
    AttachmentResponse,
    ListingPage,
    ListingResponse,
    ListingSort,
    ListingUpdate,
    OfferCreate,
    OwnListingResponse,
    PhoneReveal,
    RequestCreate,
)
from adify_api.listings.service import ListingError

router = APIRouter(prefix="/listings", tags=["Listings"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]

ERRORS = {
    status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse, "description": "Not signed in"},
    status.HTTP_403_FORBIDDEN: {"model": ErrorResponse, "description": "Not allowed"},
    status.HTTP_404_NOT_FOUND: {"model": ErrorResponse, "description": "Listing not found"},
}


def _http_error(error: ListingError) -> HTTPException:
    loc = ["body", error.field] if error.field else ["body"]
    detail = [{"loc": loc, "msg": error.msg, "type": error.type}]
    return HTTPException(status_code=error.status_code, detail=detail)


async def _own_view(session: AsyncSession, listing: Listing) -> OwnListingResponse:
    return OwnListingResponse.from_model(
        listing, locked_fields=await service.locked_fields(session, listing)
    )


def _require_role(account: VerifiedAccount, role: AccountRole, msg: str) -> None:
    if account.role != role:
        raise _http_error(ListingError(403, "role_not_allowed", msg))


@router.post(
    "/requests",
    status_code=status.HTTP_201_CREATED,
    response_model=ListingResponse,
    responses=ERRORS,
)
async def create_request(
    data: RequestCreate, account: VerifiedAccount, session: SessionDep
) -> ListingResponse:
    """A customer publishes an ad request with a budget (ADY-008)."""
    _require_role(account, AccountRole.CUSTOMER, "Only customers can create ad requests.")
    return ListingResponse.from_model(await service.create_request(session, account, data))


@router.post(
    "/offers",
    status_code=status.HTTP_201_CREATED,
    response_model=ListingResponse,
    responses=ERRORS,
)
async def create_offer(
    data: OfferCreate, account: VerifiedAccount, session: SessionDep
) -> ListingResponse:
    """A provider publishes an ad offering with a price and delivery time (ADY-009)."""
    _require_role(account, AccountRole.PROVIDER, "Only providers can create ad offerings.")
    return ListingResponse.from_model(await service.create_offer(session, account, data))


def _page(
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> tuple[int, int]:
    return limit, offset


PageDep = Annotated[tuple[int, int], Depends(_page)]


@router.get("", response_model=ListingPage)
async def list_listings(
    session: SessionDep,
    page: PageDep,
    type: Annotated[ListingType | None, Query()] = None,
    category: Annotated[ListingCategory | None, Query()] = None,
    q: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
    price_min: Annotated[Decimal | None, Query(ge=0, max_digits=10, decimal_places=2)] = None,
    price_max: Annotated[Decimal | None, Query(ge=0, max_digits=10, decimal_places=2)] = None,
    delivery_max: Annotated[int | None, Query(ge=1, le=365)] = None,
    age_min: Annotated[int | None, Query(ge=0, le=120)] = None,
    age_max: Annotated[int | None, Query(ge=0, le=120)] = None,
    country: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
    socioeconomic: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
    traits: Annotated[list[str] | None, Query()] = None,
    sort: ListingSort = ListingSort.NEWEST,
) -> ListingPage:
    """Active public listings with search and filters (FR-015, FR-016, FR-084–FR-086).

    Paused and expired listings are left out (FR-018, FR-019); they stay reachable by id.

    ``q`` matches title, description, or category without regard to case. Price
    bounds apply to the price or budget in UAH. ``delivery_max`` is the maximum
    estimated delivery time in days. Audience bounds select listings whose declared
    age range overlaps the requested one; absent limits are treated as open-ended.
    ``sort`` accepts date created (``newest``/``oldest``) or price (``price_asc``/
    ``price_desc``). Listing-owner order-history filters (FR-085) need order data
    and arrive with the order stories.
    """
    if price_min is not None and price_max is not None and price_min > price_max:
        raise _http_error(
            ListingError(422, "invalid_price_range", "The minimum price exceeds the maximum.")
        )
    if age_min is not None and age_max is not None and age_min > age_max:
        raise _http_error(
            ListingError(422, "invalid_age_range", "The minimum age exceeds the maximum.")
        )
    traits = [trait for trait in traits or [] if trait.strip()]
    if traits and (len(traits) > 20 or any(len(trait) > 50 for trait in traits)):
        raise _http_error(
            ListingError(
                422,
                "invalid_traits",
                "Use up to 20 traits of 1 to 50 characters each.",
            )
        )
    limit, offset = page
    listings, total = await service.list_listings(
        session,
        type_=type,
        category=category,
        open_only=True,
        search=q,
        price_min=price_min,
        price_max=price_max,
        delivery_max=delivery_max,
        age_min=age_min,
        age_max=age_max,
        country=country,
        socioeconomic=socioeconomic,
        traits=traits,
        sort=sort,
        limit=limit,
        offset=offset,
    )
    return ListingPage(items=[ListingResponse.from_model(item) for item in listings], total=total)


@router.get("/mine", response_model=ListingPage, responses=ERRORS)
async def my_listings(account: CurrentAccount, session: SessionDep, page: PageDep) -> ListingPage:
    """The signed-in account's own listings, newest first, including paused and expired ones."""
    limit, offset = page
    listings, total = await service.list_listings(
        session, owner_id=account.id, limit=limit, offset=offset
    )
    return ListingPage(items=[ListingResponse.from_model(item) for item in listings], total=total)


@router.get("/mine/{listing_id}", response_model=OwnListingResponse, responses=ERRORS)
async def my_listing(
    listing_id: uuid.UUID, account: CurrentAccount, session: SessionDep
) -> OwnListingResponse:
    """One of your own listings, with the fields you cannot change right now (FR-017)."""
    try:
        listing = await service.get_listing(session, listing_id)
        service.ensure_owner(listing, account)
    except ListingError as error:
        raise _http_error(error) from None
    return await _own_view(session, listing)


@router.patch(
    "/{listing_id}",
    response_model=OwnListingResponse,
    responses=ERRORS
    | {
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": "The category is locked by an active order",
        }
    },
)
async def update_listing(
    listing_id: uuid.UUID, data: ListingUpdate, account: VerifiedAccount, session: SessionDep
) -> OwnListingResponse:
    """Edit your listing (FR-017). Send only the fields to change.

    While the listing has an active order its category cannot change (`409
    category_locked`); every other field stays editable. A failed rule saves nothing.
    """
    try:
        listing = await service.get_listing(session, listing_id)
        service.ensure_owner(listing, account)
        listing = await service.update_listing(session, listing, data)
    except ListingError as error:
        raise _http_error(error) from None
    return await _own_view(session, listing)


STATE_ERRORS = ERRORS | {
    status.HTTP_409_CONFLICT: {"model": ErrorResponse, "description": "The listing has expired"}
}


@router.post("/{listing_id}/pause", response_model=OwnListingResponse, responses=STATE_ERRORS)
async def pause_listing(
    listing_id: uuid.UUID, account: CurrentAccount, session: SessionDep
) -> OwnListingResponse:
    """Pause your listing (FR-018): it leaves the marketplace and takes no new orders.

    Existing orders continue. Pausing a paused listing changes nothing. Any signed-in
    owner may pause, so a listing can always be withdrawn.
    """
    try:
        listing = await service.get_listing(session, listing_id)
        service.ensure_owner(listing, account)
        listing = await service.pause_listing(session, listing)
    except ListingError as error:
        raise _http_error(error) from None
    return await _own_view(session, listing)


@router.post("/{listing_id}/resume", response_model=OwnListingResponse, responses=STATE_ERRORS)
async def resume_listing(
    listing_id: uuid.UUID, account: VerifiedAccount, session: SessionDep
) -> OwnListingResponse:
    """Resume your paused listing (FR-018) so it takes new orders again.

    An expired listing cannot be resumed (`409 listing_expired`, FR-019). Like
    publishing, resuming needs a verified email address and phone number.
    """
    try:
        listing = await service.get_listing(session, listing_id)
        service.ensure_owner(listing, account)
        listing = await service.resume_listing(session, listing)
    except ListingError as error:
        raise _http_error(error) from None
    return await _own_view(session, listing)


@router.get("/{listing_id}", response_model=ListingResponse, responses=ERRORS)
async def get_listing(listing_id: uuid.UUID, session: SessionDep) -> ListingResponse:
    """Public listing details with the placement specification and attachments (ADY-010)."""
    try:
        return ListingResponse.from_model(await service.get_listing(session, listing_id))
    except ListingError as error:
        raise _http_error(error) from None


@router.post(
    "/{listing_id}/phone-reveal",
    response_model=PhoneReveal,
    responses=ERRORS,
)
async def reveal_phone(
    listing_id: uuid.UUID, account: VerifiedAccount, session: SessionDep
) -> PhoneReveal:
    """FR-024, FR-025: the owner's phone number, the only contact detail ever revealed."""
    try:
        listing = await service.get_listing(session, listing_id)
    except ListingError as error:
        raise _http_error(error) from None
    return PhoneReveal(phone=listing.owner.phone)


@router.post(
    "/{listing_id}/chats",
    status_code=status.HTTP_201_CREATED,
    response_model=ChatResponse,
    responses=ERRORS
    | {status.HTTP_200_OK: {"model": ChatResponse, "description": "Existing chat"}},
)
async def start_chat(
    listing_id: uuid.UUID, account: VerifiedAccount, session: SessionDep, response: Response
) -> ChatResponse:
    """FR-026: start a chat with the owner of an active, paused, or expired listing.

    Pausing or expiry stops new orders, not conversations; order creation checks that.
    Starting the same chat again returns it with `200`.
    """
    try:
        listing = await service.get_listing(session, listing_id)
        service.ensure_can_chat(listing, account)
    except ListingError as error:
        raise _http_error(error) from None
    chat, created = await chats_service.start_chat(session, listing, account)
    if not created:
        response.status_code = status.HTTP_200_OK
    return ChatResponse.for_viewer(chat, account)


@router.post(
    "/{listing_id}/attachments",
    status_code=status.HTTP_201_CREATED,
    response_model=AttachmentResponse,
    responses=ERRORS
    | {
        status.HTTP_409_CONFLICT: {"model": ErrorResponse, "description": "Too many attachments"},
        status.HTTP_413_CONTENT_TOO_LARGE: {"model": ErrorResponse, "description": "Too large"},
        status.HTTP_415_UNSUPPORTED_MEDIA_TYPE: {
            "model": ErrorResponse,
            "description": "Not a JPG, PNG, GIF, WebP, MP4, or PDF file",
        },
    },
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/octet-stream": {"schema": {"type": "string", "format": "binary"}}
            },
        }
    },
)
async def add_attachment(
    listing_id: uuid.UUID,
    request: Request,
    account: CurrentAccount,
    session: SessionDep,
    filename: Annotated[str, Query(min_length=1, max_length=255)],
) -> AttachmentResponse:
    """Attach a file to your listing. The request body is the raw file; the type is detected."""
    limit = get_settings().max_attachment_bytes
    too_large = ListingError(
        413, "attachment_too_large", f"A file can be at most {limit // (1024 * 1024)} MB."
    )
    try:
        listing = await service.get_listing(session, listing_id)
        service.ensure_owner(listing, account)
        if int(request.headers.get("content-length") or 0) > limit:
            raise too_large
        data = bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data) > limit:
                raise too_large
        attachment = await service.add_attachment(session, listing, filename, bytes(data))
    except ListingError as error:
        raise _http_error(error) from None
    return AttachmentResponse.from_model(attachment)


@router.get(
    "/{listing_id}/attachments/{attachment_id}",
    response_class=FileResponse,
    responses={status.HTTP_404_NOT_FOUND: ERRORS[status.HTTP_404_NOT_FOUND]},
)
async def download_attachment(
    listing_id: uuid.UUID, attachment_id: uuid.UUID, session: SessionDep
) -> FileResponse:
    try:
        listing = await service.get_listing(session, listing_id)
    except ListingError as error:
        raise _http_error(error) from None
    attachment = next((item for item in listing.attachments if item.id == attachment_id), None)
    path = storage.path_of(attachment_id)
    if attachment is None or not path.is_file():
        raise _http_error(
            ListingError(404, "attachment_not_found", "This attachment could not be found.")
        )
    return FileResponse(
        path,
        media_type=attachment.content_type,
        filename=attachment.filename,
        content_disposition_type="inline",
        headers={"X-Content-Type-Options": "nosniff"},
    )


@router.delete(
    "/{listing_id}/attachments/{attachment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=ERRORS,
)
async def delete_attachment(
    listing_id: uuid.UUID, attachment_id: uuid.UUID, account: CurrentAccount, session: SessionDep
) -> Response:
    try:
        listing = await service.get_listing(session, listing_id)
        service.ensure_owner(listing, account)
        await service.delete_attachment(session, listing, attachment_id)
    except ListingError as error:
        raise _http_error(error) from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)
