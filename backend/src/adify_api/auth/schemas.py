from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

from adify_api.accounts.schemas import AccountResponse

# The web keeps the refresh token in an HttpOnly cookie; the Android client stores it itself.
TokenDelivery = Literal["cookie", "body"]


class SignInRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str
    token_delivery: TokenDelivery = "cookie"

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.lower()


class RefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    refresh_token: str | None = None
    token_delivery: TokenDelivery = "cookie"


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    refresh_token: str | None = None
    account: AccountResponse
