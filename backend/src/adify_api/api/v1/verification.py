from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from adify_api.accounts.schemas import AccountResponse, ErrorResponse
from adify_api.auth.dependencies import CurrentAccount
from adify_api.core.config import get_settings
from adify_api.core.db import get_session
from adify_api.core.mail import DeliveryError
from adify_api.verification import service
from adify_api.verification.models import VerificationChannel
from adify_api.verification.schemas import CodeConfirmation, CodeSent, VerificationStatus
from adify_api.verification.service import VerificationError

router = APIRouter(prefix="/accounts/me/verification", tags=["Verification"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def _http_error(error: VerificationError) -> HTTPException:
    headers = {"Retry-After": str(error.retry_after)} if error.retry_after else None
    detail = [{"loc": ["body"], "msg": error.msg, "type": error.type}]
    return HTTPException(status_code=error.status_code, detail=detail, headers=headers)


def _error(description: str) -> dict:
    return {"model": ErrorResponse, "description": description}


@router.get(
    "",
    response_model=VerificationStatus,
    responses={status.HTTP_401_UNAUTHORIZED: _error("Not signed in")},
)
async def verification_status(account: CurrentAccount, session: SessionDep) -> VerificationStatus:
    """Whether each contact is verified and whether a usable code is waiting to be entered."""
    return VerificationStatus(
        email=await service.channel_status(session, account, VerificationChannel.EMAIL),
        phone=await service.channel_status(session, account, VerificationChannel.PHONE),
    )


@router.post(
    "/{channel}/code",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=CodeSent,
    responses={
        status.HTTP_401_UNAUTHORIZED: _error("Not signed in"),
        status.HTTP_409_CONFLICT: _error("Already verified"),
        status.HTTP_429_TOO_MANY_REQUESTS: _error("A code was sent less than a minute ago"),
        status.HTTP_503_SERVICE_UNAVAILABLE: _error("The email or SMS could not be sent"),
    },
)
async def send_code(
    channel: VerificationChannel, account: CurrentAccount, session: SessionDep
) -> CodeSent:
    """Send a six-digit code by email (Gmail, SW-002) or SMS (SW-003)."""
    try:
        code, record = await service.issue_code(session, account, channel)
    except VerificationError as error:
        raise _http_error(error) from None
    try:
        await service.deliver_code(account, channel, code)
    except DeliveryError:
        raise _http_error(
            VerificationError(
                503, "delivery_failed", f"We could not send the {channel} code. Try again later."
            )
        ) from None
    settings = get_settings()
    return CodeSent(
        channel=channel,
        destination=record.destination,
        expires_in=settings.verification_code_minutes * 60,
        resend_in=settings.verification_resend_seconds,
    )


@router.post(
    "/{channel}/confirm",
    response_model=AccountResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: _error("Wrong, expired, or used code"),
        status.HTTP_401_UNAUTHORIZED: _error("Not signed in"),
    },
)
async def confirm_code(
    channel: VerificationChannel,
    data: CodeConfirmation,
    account: CurrentAccount,
    session: SessionDep,
) -> AccountResponse:
    """Confirm the latest code; verification lasts until the address or number changes."""
    try:
        account = await service.confirm_code(session, account, channel, data.code)
    except VerificationError as error:
        raise _http_error(error) from None
    return AccountResponse.model_validate(account)
