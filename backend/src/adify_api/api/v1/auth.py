from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from adify_api.accounts.models import Account
from adify_api.accounts.schemas import AccountResponse, ErrorResponse, FieldError
from adify_api.auth.schemas import RefreshRequest, SignInRequest, TokenDelivery, TokenResponse
from adify_api.auth.service import AuthError, rotate_refresh_token, sign_in, sign_out
from adify_api.core.config import get_settings
from adify_api.core.db import get_session
from adify_api.core.security import create_access_token

router = APIRouter(prefix="/auth", tags=["Authentication"])

REFRESH_COOKIE = "adify_refresh"
REFRESH_COOKIE_PATH = "/api/v1/auth"
ERROR_STATUS = {
    "invalid_credentials": status.HTTP_401_UNAUTHORIZED,
    "invalid_refresh_token": status.HTTP_401_UNAUTHORIZED,
    "account_suspended": status.HTTP_403_FORBIDDEN,
    "account_banned": status.HTTP_403_FORBIDDEN,
}
ERROR_RESPONSES = {
    status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse, "description": "Not authenticated"},
    status.HTTP_403_FORBIDDEN: {"model": ErrorResponse, "description": "Suspended or banned"},
}

SessionDep = Annotated[AsyncSession, Depends(get_session)]
RefreshCookie = Annotated[str | None, Cookie(alias=REFRESH_COOKIE)]


def _error(error: AuthError) -> JSONResponse:
    body = ErrorResponse(detail=[FieldError(loc=["body"], msg=error.msg, type=error.type)])
    return JSONResponse(status_code=ERROR_STATUS[error.type], content=body.model_dump())


def _tokens(account: Account, refresh_token: str, delivery: TokenDelivery) -> JSONResponse:
    settings = get_settings()
    body = TokenResponse(
        access_token=create_access_token(str(account.id), account.role),
        expires_in=settings.access_token_minutes * 60,
        refresh_token=refresh_token if delivery == "body" else None,
        account=AccountResponse.model_validate(account),
    )
    response = JSONResponse(content=body.model_dump(mode="json"))
    if delivery == "cookie":
        response.set_cookie(
            REFRESH_COOKIE,
            refresh_token,
            max_age=settings.refresh_token_days * 24 * 60 * 60,
            path=REFRESH_COOKIE_PATH,
            secure=settings.refresh_cookie_secure,
            httponly=True,
            samesite="lax",
        )
    return response


@router.post("/sign-in", response_model=TokenResponse, responses=ERROR_RESPONSES)
async def sign_in_with_password(data: SignInRequest, session: SessionDep) -> JSONResponse:
    """FR-007: authenticate with email and password; MFA is out of scope for the MVP."""
    try:
        account, refresh_token = await sign_in(session, data.email, data.password)
    except AuthError as error:
        return _error(error)
    return _tokens(account, refresh_token, data.token_delivery)


@router.post("/refresh", response_model=TokenResponse, responses=ERROR_RESPONSES)
async def refresh(
    session: SessionDep, cookie: RefreshCookie = None, data: RefreshRequest | None = None
) -> JSONResponse:
    """Exchange a refresh token for a new access token; the refresh token is rotated."""
    data = data or RefreshRequest()
    try:
        account, refresh_token = await rotate_refresh_token(session, data.refresh_token or cookie)
    except AuthError as error:
        response = _error(error)
        response.delete_cookie(REFRESH_COOKIE, path=REFRESH_COOKIE_PATH)
        return response
    return _tokens(account, refresh_token, data.token_delivery)


@router.post("/sign-out", status_code=status.HTTP_204_NO_CONTENT)
async def sign_out_session(
    session: SessionDep, cookie: RefreshCookie = None, data: RefreshRequest | None = None
) -> Response:
    """Revoke the refresh token; access tokens expire on their own within minutes."""
    await sign_out(session, (data.refresh_token if data else None) or cookie)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_COOKIE_PATH)
    return response
