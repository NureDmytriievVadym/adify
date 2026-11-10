import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from adify_api.accounts.schemas import ErrorResponse
from adify_api.api.v1.chats import http_error as chat_http_error
from adify_api.auth.dependencies import CurrentAccount, VerifiedAccount
from adify_api.chats import service as chats
from adify_api.chats.service import ChatError
from adify_api.core.db import get_session
from adify_api.orders import service
from adify_api.orders.schemas import OrderCreate, OrderResponse
from adify_api.orders.service import OrderError

router = APIRouter(tags=["Orders"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]

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
