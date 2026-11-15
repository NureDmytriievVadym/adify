"""add listing expiry reasons and account last sign-in

Revision ID: 0015
Revises: 0014
Create Date: 2026-11-14 15:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: str | Sequence[str] | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("accounts", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))
    # Accounts that existed before sign-ins were recorded must not be treated as
    # inactive on the first run; from now on every successful sign-in updates the field.
    op.execute("UPDATE accounts SET last_login_at = now() WHERE last_login_at IS NULL")
    op.add_column("listings", sa.Column("expired_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "listings",
        sa.Column(
            "expired_reason",
            sa.Enum(
                "date",
                "inactivity",
                name="expiry_reason",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            nullable=True,
        ),
    )
    op.add_column(
        "listings", sa.Column("expiry_notified_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("listings", "expiry_notified_at")
    op.drop_column("listings", "expired_reason")
    op.drop_column("listings", "expired_at")
    op.drop_column("accounts", "last_login_at")
