"""create verification codes

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-01 20:56:20.235867
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "verification_codes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column(
            "channel",
            sa.Enum(
                "email",
                "phone",
                name="verification_channel",
                native_enum=False,
                create_constraint=True,
                length=10,
            ),
            nullable=False,
        ),
        sa.Column("destination", sa.String(length=254), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["account_id"], ["accounts.id"], name=op.f("fk_verification_codes_account_id_accounts")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_verification_codes")),
    )
    op.create_index(
        op.f("ix_verification_codes_account_id"), "verification_codes", ["account_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_verification_codes_account_id"), table_name="verification_codes")
    op.drop_table("verification_codes")
