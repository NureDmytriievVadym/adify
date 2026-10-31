import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from adify_api.accounts.models import AccountRole
from adify_api.accounts.schemas import ErrorResponse
from adify_api.auth.dependencies import CurrentAccount
from adify_api.core.config import get_settings
from adify_api.core.db import get_session
from adify_api.listings import service, storage
from adify_api.listings.models import ListingCategory, ListingType
from adify_api.listings.schemas import (
    AttachmentResponse,
    ListingPage,
    ListingResponse,
    OfferCreate,
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
    detail = [{"loc": ["body"], "msg": error.msg, "type": error.type}]
    return HTTPException(status_code=error.status_code, detail=detail)


def _require_role(account: CurrentAccount, role: AccountRole, msg: str) -> None:
    if account.role != role:
        raise _http_error(ListingError(403, "role_not_allowed", msg))


@router.post(
    "/requests",
    status_code=status.HTTP_201_CREATED,
    response_model=ListingResponse,
    responses=ERRORS,
)
async def create_request(
    data: RequestCreate, account: CurrentAccount, session: SessionDep
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
    data: OfferCreate, account: CurrentAccount, session: SessionDep
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
) -> ListingPage:
    """Public listings, newest first, optionally filtered by type and category."""
    limit, offset = page
    listings, total = await service.list_listings(
        session, type_=type, category=category, limit=limit, offset=offset
    )
    return ListingPage(items=[ListingResponse.from_model(item) for item in listings], total=total)


@router.get("/mine", response_model=ListingPage, responses=ERRORS)
async def my_listings(account: CurrentAccount, session: SessionDep, page: PageDep) -> ListingPage:
    """The signed-in account's own listings, newest first."""
    limit, offset = page
    listings, total = await service.list_listings(
        session, owner_id=account.id, limit=limit, offset=offset
    )
    return ListingPage(items=[ListingResponse.from_model(item) for item in listings], total=total)


@router.get("/{listing_id}", response_model=ListingResponse, responses=ERRORS)
async def get_listing(listing_id: uuid.UUID, session: SessionDep) -> ListingResponse:
    """Public listing details with the placement specification and attachments (ADY-010)."""
    try:
        return ListingResponse.from_model(await service.get_listing(session, listing_id))
    except ListingError as error:
        raise _http_error(error) from None


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
