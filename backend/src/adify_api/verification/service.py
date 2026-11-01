import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from adify_api.accounts.models import Account
from adify_api.core.config import get_settings
from adify_api.core.mail import send_email
from adify_api.core.sms import send_sms
from adify_api.verification.models import VerificationChannel, VerificationCode
from adify_api.verification.schemas import ChannelStatus


class VerificationError(Exception):
    def __init__(self, status_code: int, type_: str, msg: str, retry_after: int | None = None):
        super().__init__(msg)
        self.status_code = status_code
        self.type = type_
        self.msg = msg
        self.retry_after = retry_after


def _aware(moment: datetime) -> datetime:
    # SQLite, used by the tests, returns naive datetimes; PostgreSQL keeps the zone.
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def _hash(account: Account, channel: VerificationChannel, code: str) -> str:
    # Keyed, because six digits are trivial to brute-force from a plain hash.
    message = f"{account.id}:{channel}:{code}".encode()
    return hmac.new(get_settings().jwt_secret.encode(), message, hashlib.sha256).hexdigest()


def destination(account: Account, channel: VerificationChannel) -> str:
    return account.email if channel == VerificationChannel.EMAIL else account.phone


def is_verified(account: Account, channel: VerificationChannel) -> bool:
    return (
        account.email_verified if channel == VerificationChannel.EMAIL else account.phone_verified
    )


async def _latest(
    session: AsyncSession, account: Account, channel: VerificationChannel
) -> VerificationCode | None:
    return await session.scalar(
        select(VerificationCode)
        .where(VerificationCode.account_id == account.id, VerificationCode.channel == channel)
        .order_by(VerificationCode.created_at.desc())
        .limit(1)
    )


def _resend_in(latest: VerificationCode | None, now: datetime) -> int:
    if latest is None:
        return 0
    elapsed = (now - _aware(latest.created_at)).total_seconds()
    return max(0, get_settings().verification_resend_seconds - int(elapsed))


async def channel_status(
    session: AsyncSession, account: Account, channel: VerificationChannel
) -> ChannelStatus:
    """Lets clients show the code field only when a usable code is out."""
    now = datetime.now(UTC)
    latest = await _latest(session, account, channel)
    usable = (
        latest is not None
        and latest.used_at is None
        and latest.destination == destination(account, channel)
        and _aware(latest.expires_at) > now
    )
    verified = is_verified(account, channel)
    return ChannelStatus(
        verified=verified,
        destination=destination(account, channel),
        code_sent=usable and not verified,
        resend_in=0 if verified else _resend_in(latest, now),
    )


async def issue_code(
    session: AsyncSession, account: Account, channel: VerificationChannel
) -> tuple[str, VerificationCode]:
    """Create a code, replacing any earlier one for the channel; delivery is separate."""
    if is_verified(account, channel):
        raise VerificationError(409, "already_verified", f"Your {channel} is already verified.")
    settings = get_settings()
    now = datetime.now(UTC)
    if wait := _resend_in(await _latest(session, account, channel), now):
        raise VerificationError(
            429, "resend_too_soon", f"Wait {wait} seconds before requesting a new code.", wait
        )
    await session.execute(
        update(VerificationCode)
        .where(
            VerificationCode.account_id == account.id,
            VerificationCode.channel == channel,
            VerificationCode.used_at.is_(None),
        )
        .values(used_at=now)
    )
    code = f"{secrets.randbelow(1_000_000):06d}"
    record = VerificationCode(
        account_id=account.id,
        channel=channel,
        destination=destination(account, channel),
        code_hash=_hash(account, channel, code),
        expires_at=now + timedelta(minutes=settings.verification_code_minutes),
        created_at=now,
    )
    session.add(record)
    await session.commit()
    return code, record


async def deliver_code(account: Account, channel: VerificationChannel, code: str) -> None:
    minutes = get_settings().verification_code_minutes
    if channel == VerificationChannel.PHONE:
        await send_sms(
            account.phone, f"Your Adify code is {code}. It expires in {minutes} minutes."
        )
        return
    link = f"{get_settings().web_base_url}/account?email_code={code}#verification"
    await send_email(
        account.email,
        f"{code} is your Adify verification code",
        f"Hello {account.display_name},\n\n"
        f"Your Adify email verification code is {code}. It expires in {minutes} minutes.\n\n"
        f"You can also open this link while signed in:\n{link}\n\n"
        "If you did not create an Adify account, you can ignore this email.\n",
    )


async def confirm_code(
    session: AsyncSession, account: Account, channel: VerificationChannel, code: str
) -> Account:
    if is_verified(account, channel):
        return account
    record = await _latest(session, account, channel)
    if record is None or record.destination != destination(account, channel):
        raise VerificationError(400, "code_not_requested", "Request a verification code first.")
    if record.used_at is not None:
        raise VerificationError(
            400, "code_used", "This code is no longer valid. Request a new one."
        )
    if _aware(record.expires_at) <= datetime.now(UTC):
        raise VerificationError(400, "code_expired", "This code has expired. Request a new one.")
    if not hmac.compare_digest(record.code_hash, _hash(account, channel, code)):
        record.attempts += 1
        left = get_settings().verification_max_attempts - record.attempts
        if left <= 0:
            record.used_at = datetime.now(UTC)
            await session.commit()
            raise VerificationError(
                400, "code_attempts_exceeded", "Too many incorrect attempts. Request a new code."
            )
        await session.commit()
        attempts = "attempt" if left == 1 else "attempts"
        raise VerificationError(
            400, "code_incorrect", f"This code is incorrect. {left} {attempts} left."
        )
    record.used_at = datetime.now(UTC)
    if channel == VerificationChannel.EMAIL:
        account.email_verified = True
    else:
        account.phone_verified = True
    await session.commit()
    await session.refresh(account)
    return account
