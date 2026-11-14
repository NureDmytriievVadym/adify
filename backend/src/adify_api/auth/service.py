from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from adify_api.accounts.models import Account, AccountStatus
from adify_api.auth.models import PasswordResetToken, RefreshToken
from adify_api.core.config import get_settings
from adify_api.core.mail import send_email
from adify_api.core.security import (
    dummy_password_hash,
    hash_password,
    hash_token,
    new_token,
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
INVALID_RESET_LINK = AuthError(
    "reset_link_invalid", "This link has expired or has already been used. Request a new one."
)


def ensure_active(account: Account) -> None:
    if account.status in STATUS_ERRORS:
        raise AuthError(*STATUS_ERRORS[account.status])


def _aware(moment: datetime) -> datetime:
    # SQLite, used by the tests, returns naive datetimes; PostgreSQL keeps the zone.
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


async def _issue_refresh_token(session: AsyncSession, account: Account) -> str:
    token = new_token()
    session.add(
        RefreshToken(
            account_id=account.id,
            token_hash=hash_token(token),
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
    # FR-022: the inactivity clock starts at a successful sign-in, not at a token refresh.
    account.last_login_at = datetime.now(UTC)
    return account, await _issue_refresh_token(session, account)


async def _active_refresh_token(session: AsyncSession, token: str | None) -> RefreshToken:
    if not token:
        raise INVALID_REFRESH_TOKEN
    stored = await session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_token(token))
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


async def request_password_reset(session: AsyncSession, email: str) -> tuple[Account, str] | None:
    """Issue a reset link for a verified email; None means nothing should be sent.

    The caller answers the same way either way, so the response never reveals
    whether an email is registered or verified.
    """
    account = await session.scalar(select(Account).where(Account.email == email))
    if account is None or not account.email_verified:
        return None
    settings = get_settings()
    now = datetime.now(UTC)
    latest = await session.scalar(
        select(PasswordResetToken)
        .where(PasswordResetToken.account_id == account.id)
        .order_by(PasswordResetToken.created_at.desc())
        .limit(1)
    )
    if latest is not None and (now - _aware(latest.created_at)).total_seconds() < (
        settings.password_reset_resend_seconds
    ):
        return None
    # Only the newest link works.
    await session.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.account_id == account.id, PasswordResetToken.used_at.is_(None))
        .values(used_at=now)
    )
    token = new_token()
    session.add(
        PasswordResetToken(
            account_id=account.id,
            token_hash=hash_token(token),
            expires_at=now + timedelta(minutes=settings.password_reset_minutes),
            created_at=now,
        )
    )
    await session.commit()
    return account, token


async def deliver_password_reset(account: Account, token: str) -> None:
    settings = get_settings()
    link = f"{settings.web_base_url}/reset-password?token={token}"
    await send_email(
        account.email,
        "Reset your Adify password",
        f"Hello {account.display_name},\n\n"
        f"Open this link to set a new Adify password:\n{link}\n\n"
        f"The link works once and expires in {settings.password_reset_minutes} minutes.\n\n"
        "If you did not ask to reset your password, you can ignore this email; "
        "your password stays the same.\n",
    )


async def reset_password(session: AsyncSession, token: str, password: str) -> None:
    now = datetime.now(UTC)
    stored = await session.scalar(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == hash_token(token))
    )
    if stored is None or stored.used_at is not None or _aware(stored.expires_at) <= now:
        raise INVALID_RESET_LINK
    # Conditional update, so two concurrent uses of one link cannot both succeed.
    claimed = await session.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.id == stored.id, PasswordResetToken.used_at.is_(None))
        .values(used_at=now)
    )
    if claimed.rowcount != 1:
        await session.rollback()
        raise INVALID_RESET_LINK
    account = await session.get_one(Account, stored.account_id)
    account.password_hash = hash_password(password)
    # Whoever had the old password loses every session it opened.
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.account_id == account.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    await session.commit()
