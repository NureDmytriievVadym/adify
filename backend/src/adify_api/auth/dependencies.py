import uuid
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from adify_api.accounts.models import Account
from adify_api.auth.service import AuthError, ensure_active
from adify_api.core.db import get_session
from adify_api.core.security import decode_access_token

bearer = HTTPBearer(auto_error=False)


def auth_error(status_code: int, type_: str, msg: str) -> HTTPException:
    headers = {"WWW-Authenticate": "Bearer"} if status_code == 401 else None
    return HTTPException(
        status_code=status_code,
        detail=[{"loc": ["header", "Authorization"], "msg": msg, "type": type_}],
        headers=headers,
    )


async def get_current_account(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Account:
    if credentials is None:
        raise auth_error(401, "not_authenticated", "Sign in to continue.")
    try:
        account_id = uuid.UUID(str(decode_access_token(credentials.credentials)["sub"]))
    except (jwt.PyJWTError, ValueError):
        raise auth_error(
            401, "invalid_access_token", "Your session has ended. Sign in again."
        ) from None
    account = await session.get(Account, account_id)
    if account is None:
        raise auth_error(401, "invalid_access_token", "Your session has ended. Sign in again.")
    try:
        ensure_active(account)
    except AuthError as error:
        raise auth_error(403, error.type, error.msg) from None
    return account


CurrentAccount = Annotated[Account, Depends(get_current_account)]
