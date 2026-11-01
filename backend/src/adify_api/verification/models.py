import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from adify_api.core.db import Base


class VerificationChannel(StrEnum):
    EMAIL = "email"
    PHONE = "phone"


class VerificationCode(Base):
    __tablename__ = "verification_codes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id"), index=True)
    channel: Mapped[VerificationChannel] = mapped_column(
        Enum(
            VerificationChannel,
            name="verification_channel",
            native_enum=False,
            create_constraint=True,
            length=10,
            values_callable=lambda members: [member.value for member in members],
        )
    )
    # The address or number the code was sent to: a code stops counting once it changes (FR-006).
    destination: Mapped[str] = mapped_column(String(254))
    code_hash: Mapped[str] = mapped_column(String(64))
    attempts: Mapped[int] = mapped_column(default=0)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
