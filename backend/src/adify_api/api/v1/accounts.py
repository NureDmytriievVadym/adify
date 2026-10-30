from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from adify_api.accounts.schemas import AccountResponse, ErrorResponse, RegistrationRequest
from adify_api.accounts.service import RegistrationError, register_account
from adify_api.core.db import get_session

router = APIRouter(prefix="/accounts", tags=["Accounts"])

ERROR_STATUS = {"banned": status.HTTP_403_FORBIDDEN, "taken": status.HTTP_409_CONFLICT}


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=AccountResponse,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Email or phone of a banned account",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": "Email or phone already registered",
        },
    },
)
async def register(
    data: RegistrationRequest, session: Annotated[AsyncSession, Depends(get_session)]
) -> AccountResponse | JSONResponse:
    """Register a customer or provider account; staff accounts are never created here."""
    try:
        account = await register_account(session, data)
    except RegistrationError as error:
        body = ErrorResponse(detail=error.errors)
        return JSONResponse(status_code=ERROR_STATUS[error.kind], content=body.model_dump())
    return AccountResponse.model_validate(account)
