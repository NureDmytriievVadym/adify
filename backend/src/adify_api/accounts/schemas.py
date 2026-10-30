import re
import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    StringConstraints,
    field_validator,
)
from pydantic_core import PydanticCustomError

from adify_api.accounts.models import AccountRole, AccountStatus

UKRAINIAN_PHONE = re.compile(r"\+380\d{9}")
PHONE_SEPARATORS = re.compile(r"[\s()-]")


class RegistrationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
    ]
    email: EmailStr
    phone: str
    role: Literal["customer", "provider"]
    password: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.lower()

    @field_validator("phone")
    @classmethod
    def ukrainian_phone(cls, value: str) -> str:
        phone = PHONE_SEPARATORS.sub("", value)
        if not UKRAINIAN_PHONE.fullmatch(phone):
            raise PydanticCustomError(
                "phone_not_ukrainian",
                "Enter a Ukrainian phone number in the format +380XXXXXXXXX.",
            )
        return phone

    @field_validator("role", mode="before")
    @classmethod
    def single_role(cls, value: object) -> object:
        if not isinstance(value, str):
            raise PydanticCustomError(
                "role_not_single", "Choose exactly one role: customer or provider."
            )
        return value

    @field_validator("password")
    @classmethod
    def password_policy(cls, value: str) -> str:
        if (
            len(value) < 8
            or not any(char.isalpha() for char in value)
            or not any(char.isdecimal() for char in value)
        ):
            raise PydanticCustomError(
                "password_policy",
                "Use at least 8 characters, including at least one letter and one digit.",
            )
        # bcrypt only accepts the first 72 bytes of a password.
        if len(value.encode()) > 72:
            raise PydanticCustomError("password_too_long", "Use at most 72 bytes.")
        return value


class AccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    display_name: str
    email: str
    phone: str
    role: AccountRole
    status: AccountStatus
    email_verified: bool
    phone_verified: bool
    created_at: datetime


class FieldError(BaseModel):
    loc: list[str]
    msg: str
    type: str


class ErrorResponse(BaseModel):
    detail: list[FieldError]
