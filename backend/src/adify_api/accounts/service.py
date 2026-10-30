from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from adify_api.accounts.models import Account, AccountBan, AccountRole
from adify_api.accounts.schemas import FieldError, RegistrationRequest
from adify_api.core.security import hash_password


class RegistrationError(Exception):
    def __init__(self, kind: str, errors: list[FieldError]) -> None:
        super().__init__(kind)
        self.kind = kind
        self.errors = errors


def _field_error(field: str, type_: str, msg: str) -> FieldError:
    return FieldError(loc=["body", field], msg=msg, type=type_)


async def _banned_contacts(session: AsyncSession, email: str, phone: str) -> list[FieldError]:
    bans = (
        await session.scalars(
            select(AccountBan).where(or_(AccountBan.email == email, AccountBan.phone == phone))
        )
    ).all()
    errors = []
    if any(ban.email == email for ban in bans):
        errors.append(
            _field_error("email", "email_banned", "This email address belongs to a banned account.")
        )
    if any(ban.phone == phone for ban in bans):
        errors.append(
            _field_error("phone", "phone_banned", "This phone number belongs to a banned account.")
        )
    return errors


async def _taken_contacts(session: AsyncSession, email: str, phone: str) -> list[FieldError]:
    accounts = (
        await session.scalars(
            select(Account).where(or_(Account.email == email, Account.phone == phone))
        )
    ).all()
    errors = []
    if any(account.email == email for account in accounts):
        errors.append(
            _field_error("email", "email_taken", "An account with this email address exists.")
        )
    if any(account.phone == phone for account in accounts):
        errors.append(
            _field_error("phone", "phone_taken", "An account with this phone number exists.")
        )
    return errors


async def register_account(session: AsyncSession, data: RegistrationRequest) -> Account:
    # Bans are checked first: a banned account still owns its contacts and would look "taken".
    if errors := await _banned_contacts(session, data.email, data.phone):
        raise RegistrationError("banned", errors)
    if errors := await _taken_contacts(session, data.email, data.phone):
        raise RegistrationError("taken", errors)

    account = Account(
        display_name=data.display_name,
        email=data.email,
        phone=data.phone,
        password_hash=hash_password(data.password),
        role=AccountRole(data.role),
    )
    session.add(account)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise RegistrationError(
            "taken", await _taken_contacts(session, data.email, data.phone)
        ) from None
    await session.refresh(account)
    return account
