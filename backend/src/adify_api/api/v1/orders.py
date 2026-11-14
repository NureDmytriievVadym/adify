import uuid
from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from adify_api.accounts.models import Account
from adify_api.accounts.schemas import ErrorResponse
from adify_api.api.v1.chats import http_error as chat_http_error
from adify_api.auth.dependencies import CurrentAccount, VerifiedAccount
from adify_api.chats import service as chats
from adify_api.chats.service import ChatError
from adify_api.core.db import get_session
from adify_api.orders import review, service, workflow
from adify_api.orders.models import Order
from adify_api.orders.schemas import ChangeRequestCreate, OrderCreate, OrderResponse
from adify_api.orders.service import OrderError
from adify_api.payments.mono import MonoClient, get_mono

router = APIRouter(tags=["Orders"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
MonoDep = Annotated[MonoClient | None, Depends(get_mono)]

ERRORS = {
    status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse, "description": "Not signed in"},
    status.HTTP_403_FORBIDDEN: {"model": ErrorResponse, "description": "Not allowed"},
    status.HTTP_404_NOT_FOUND: {"model": ErrorResponse, "description": "Not found"},
}


def http_error(error: OrderError) -> HTTPException:
    detail = [{"loc": ["body"], "msg": error.msg, "type": error.type}]
    return HTTPException(status_code=error.status_code, detail=detail)


@router.post(
    "/chats/{chat_id}/orders",
    status_code=status.HTTP_201_CREATED,
    response_model=OrderResponse,
    responses=ERRORS
    | {
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": "The listing is paused, expired, or deleted",
        }
    },
)
async def create_order(
    chat_id: uuid.UUID, data: OrderCreate, account: VerifiedAccount, session: SessionDep
) -> OrderResponse:
    """FR-031, FR-033: the listing owner creates an order awaiting payment (FR-035)."""
    try:
        chat = await chats.get_chat(session, chat_id, account)
        order = await service.create_order(session, chat, account, data)
    except ChatError as error:
        raise chat_http_error(error) from None
    except OrderError as error:
        raise http_error(error) from None
    return OrderResponse.for_viewer(order, account)


@router.get("/chats/{chat_id}/orders", response_model=list[OrderResponse], responses=ERRORS)
async def chat_orders(
    chat_id: uuid.UUID, account: CurrentAccount, session: SessionDep
) -> list[OrderResponse]:
    """Orders created in this chat, newest first, for its two participants."""
    try:
        chat = await chats.get_chat(session, chat_id, account)
    except ChatError as error:
        raise chat_http_error(error) from None
    return [OrderResponse.for_viewer(o, account) for o in await service.chat_orders(session, chat)]


@router.get("/orders", response_model=list[OrderResponse], responses=ERRORS)
async def my_orders(account: CurrentAccount, session: SessionDep) -> list[OrderResponse]:
    """The signed-in user's orders as customer or provider, newest first."""
    return [OrderResponse.for_viewer(o, account) for o in await service.my_orders(session, account)]


@router.get("/orders/{order_id}", response_model=OrderResponse, responses=ERRORS)
async def get_order(
    order_id: uuid.UUID, account: CurrentAccount, session: SessionDep
) -> OrderResponse:
    """One order for its customer and provider only."""
    try:
        order = await service.get_order(session, order_id, account)
    except OrderError as error:
        raise http_error(error) from None
    return OrderResponse.for_viewer(order, account)


@router.post(
    "/orders/{order_id}/start",
    response_model=OrderResponse,
    responses=ERRORS
    | {
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": "Not paid, or a validated creative is missing",
        },
        status.HTTP_502_BAD_GATEWAY: {"model": ErrorResponse, "description": "Mono failed"},
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": ErrorResponse,
            "description": "Payments are not configured",
        },
    },
)
async def start_work(
    order_id: uuid.UUID, account: VerifiedAccount, session: SessionDep, mono: MonoDep
) -> OrderResponse:
    """FR-039: the provider starts a paid order; Mono charges the held funds (FR-056).

    Blocked while the order needs a validated creative it does not have (FR-124).
    """
    try:
        order = await service.get_order(session, order_id, account)
        order = await workflow.start_work(session, order, account, mono)
    except OrderError as error:
        raise http_error(error) from None
    return OrderResponse.for_viewer(order, account)


REVIEW_ERRORS = ERRORS | {
    status.HTTP_409_CONFLICT: {
        "model": ErrorResponse,
        "description": "The order is not in the required state",
    }
}


async def _act(
    session: AsyncSession,
    order_id: uuid.UUID,
    account: Account,
    action: Callable[[Order], Awaitable[Order]],
) -> OrderResponse:
    """Loads the order for a participant, applies one review action, and answers with it."""
    try:
        order = await service.get_order(session, order_id, account)
        order = await action(order)
    except OrderError as error:
        raise http_error(error) from None
    return OrderResponse.for_viewer(order, account)


@router.post("/orders/{order_id}/review", response_model=OrderResponse, responses=REVIEW_ERRORS)
async def submit_for_review(
    order_id: uuid.UUID, account: VerifiedAccount, session: SessionDep
) -> OrderResponse:
    """FR-040: the provider submits work in progress; the order goes to review."""
    return await _act(
        session, order_id, account, lambda o: review.submit_for_review(session, o, account)
    )


@router.post("/orders/{order_id}/accept", response_model=OrderResponse, responses=REVIEW_ERRORS)
async def accept_work(
    order_id: uuid.UUID, account: VerifiedAccount, session: SessionDep
) -> OrderResponse:
    """FR-043: the customer accepts the submitted work; the order is done."""
    return await _act(session, order_id, account, lambda o: review.accept_work(session, o, account))


@router.post(
    "/orders/{order_id}/change-requests",
    status_code=status.HTTP_201_CREATED,
    response_model=OrderResponse,
    responses=REVIEW_ERRORS,
)
async def request_changes(
    order_id: uuid.UUID, data: ChangeRequestCreate, account: VerifiedAccount, session: SessionDep
) -> OrderResponse:
    """FR-042: the customer asks for changes; one request waits for an answer at a time."""
    return await _act(
        session,
        order_id,
        account,
        lambda o: review.request_changes(session, o, account, data.message),
    )


@router.post(
    "/orders/{order_id}/change-requests/{request_id}/agree",
    response_model=OrderResponse,
    responses=REVIEW_ERRORS,
)
async def agree_to_changes(
    order_id: uuid.UUID, request_id: uuid.UUID, account: VerifiedAccount, session: SessionDep
) -> OrderResponse:
    """FR-044: the provider agrees to make the changes; the order is back in progress."""
    return await _act(
        session,
        order_id,
        account,
        lambda o: review.answer_change_request(session, o, account, request_id, agree=True),
    )


@router.post(
    "/orders/{order_id}/change-requests/{request_id}/decline",
    response_model=OrderResponse,
    responses=REVIEW_ERRORS,
)
async def decline_changes(
    order_id: uuid.UUID, request_id: uuid.UUID, account: VerifiedAccount, session: SessionDep
) -> OrderResponse:
    """FR-044: the provider declines the changes; the order stays in review."""
    return await _act(
        session,
        order_id,
        account,
        lambda o: review.answer_change_request(session, o, account, request_id, agree=False),
    )
