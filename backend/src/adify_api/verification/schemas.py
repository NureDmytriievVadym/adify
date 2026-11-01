from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

from adify_api.verification.models import VerificationChannel


class CodeSent(BaseModel):
    channel: VerificationChannel
    destination: str
    expires_in: int
    resend_in: int


class CodeConfirmation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^\d{6}$")]


class ChannelStatus(BaseModel):
    verified: bool
    destination: str
    code_sent: bool
    resend_in: int


class VerificationStatus(BaseModel):
    email: ChannelStatus
    phone: ChannelStatus
