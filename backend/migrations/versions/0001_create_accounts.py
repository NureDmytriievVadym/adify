"""create accounts

Revision ID: 0001
Revises:
Create Date: 2026-10-30 15:45:29.057276
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("phone", sa.String(length=13), nullable=False),
        sa.Column("password_hash", sa.String(length=60), nullable=False),
        sa.Column(
            "role",
            sa.Enum(
                "customer",
                "provider",
                "moderator",
                "administrator",
                name="account_role",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "active",
                "suspended",
                "banned",
                name="account_status",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("email_verified", sa.Boolean(), nullable=False),
        sa.Column("phone_verified", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_accounts")),
        sa.UniqueConstraint("email", name=op.f("uq_accounts_email")),
        sa.UniqueConstraint("phone", name=op.f("uq_accounts_phone")),
    )
    op.create_table(
        "account_bans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("phone", sa.String(length=13), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["account_id"], ["accounts.id"], name=op.f("fk_account_bans_account_id_accounts")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_account_bans")),
    )
    op.create_index(
        op.f("ix_account_bans_account_id"), "account_bans", ["account_id"], unique=False
    )
    op.create_index(op.f("ix_account_bans_email"), "account_bans", ["email"], unique=False)
    op.create_index(op.f("ix_account_bans_phone"), "account_bans", ["phone"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_account_bans_phone"), table_name="account_bans")
    op.drop_index(op.f("ix_account_bans_email"), table_name="account_bans")
    op.drop_index(op.f("ix_account_bans_account_id"), table_name="account_bans")
    op.drop_table("account_bans")
    op.drop_table("accounts")
