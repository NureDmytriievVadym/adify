from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from adify_api.accounts.models import Account, AccountStatus
from adify_api.auth.models import RefreshToken
from adify_api.core.config import get_settings
from adify_api.core.security import (
    dummy_password_hash,
    hash_refresh_token,
    new_refresh_token,
    verify_password,
)

STATUS_ERRORS = {
    AccountStatus.SUSPENDED: ("account_suspended", "This account is suspended."),
    AccountStatus.BANNED: ("account_banned", "This account is banned."),
}


class AuthError(Exception):
    def __init__(self, type_: str, msg: str) -> None:
        super().__init__(msg)
        self.type = type_
        self.msg = msg


INVALID_CREDENTIALS = AuthError("invalid_credentials", "Incorrect email address or password.")
INVALID_REFRESH_TOKEN = AuthError("invalid_refresh_token", "Your session has ended. Sign in again.")


def ensure_active(account: Account) -> None:
    if account.status in STATUS_ERRORS:
        raise AuthError(*STATUS_ERRORS[account.status])


def _aware(moment: datetime) -> datetime:
    # SQLite, used by the tests, returns naive datetimes; PostgreSQL keeps the zone.
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


async def _issue_refresh_token(session: AsyncSession, account: Account) -> str:
    token = new_refresh_token()
    session.add(
        RefreshToken(
            account_id=account.id,
            token_hash=hash_refresh_token(token),
            expires_at=datetime.now(UTC) + timedelta(days=get_settings().refresh_token_days),
        )
    )
    await session.commit()
    return token


async def sign_in(session: AsyncSession, email: str, password: str) -> tuple[Account, str]:
    account = await session.scalar(select(Account).where(Account.email == email))
    if account is None:
        verify_password(password, dummy_password_hash())
        raise INVALID_CREDENTIALS
    if not verify_password(password, account.password_hash):
        raise INVALID_CREDENTIALS
    # Status is revealed only to someone who knows the password.
    ensure_active(account)
    return account, await _issue_refresh_token(session, account)


async def _active_refresh_token(session: AsyncSession, token: str | None) -> RefreshToken:
    if not token:
        raise INVALID_REFRESH_TOKEN
    stored = await session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(token))
    )
    if (
        stored is None
        or stored.revoked_at is not None
        or _aware(stored.expires_at) <= datetime.now(UTC)
    ):
        raise INVALID_REFRESH_TOKEN
    return stored


async def rotate_refresh_token(session: AsyncSession, token: str | None) -> tuple[Account, str]:
    stored = await _active_refresh_token(session, token)
    account = await session.get_one(Account, stored.account_id)
    ensure_active(account)
    stored.revoked_at = datetime.now(UTC)
    return account, await _issue_refresh_token(session, account)


async def sign_out(session: AsyncSession, token: str | None) -> None:
    try:
        stored = await _active_refresh_token(session, token)
    except AuthError:
        return
    stored.revoked_at = datetime.now(UTC)
    await session.commit()
