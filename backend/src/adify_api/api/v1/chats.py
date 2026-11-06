import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from adify_api.accounts.schemas import ErrorResponse
from adify_api.auth.dependencies import CurrentAccount
from adify_api.chats import service
from adify_api.chats.schemas import ChatResponse
from adify_api.chats.service import ChatError
from adify_api.core.db import get_session

router = APIRouter(prefix="/chats", tags=["Chats"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]

ERRORS = {
    status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse, "description": "Not signed in"},
    status.HTTP_403_FORBIDDEN: {"model": ErrorResponse, "description": "Not a participant"},
    status.HTTP_404_NOT_FOUND: {"model": ErrorResponse, "description": "Chat not found"},
}


def http_error(error: ChatError) -> HTTPException:
    detail = [{"loc": ["path"], "msg": error.msg, "type": error.type}]
    return HTTPException(status_code=error.status_code, detail=detail)


@router.get("", response_model=list[ChatResponse], responses=ERRORS)
async def my_chats(account: CurrentAccount, session: SessionDep) -> list[ChatResponse]:
    """The signed-in user's chats, newest first."""
    chats = await service.list_chats(session, account)
    return [ChatResponse.for_viewer(chat, account) for chat in chats]


@router.get("/{chat_id}", response_model=ChatResponse, responses=ERRORS)
async def get_chat(
    chat_id: uuid.UUID, account: CurrentAccount, session: SessionDep
) -> ChatResponse:
    """One chat, for its two participants only (FR-027)."""
    try:
        chat = await service.get_chat(session, chat_id, account)
    except ChatError as error:
        raise http_error(error) from None
    return ChatResponse.for_viewer(chat, account)
