"""create chats

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-06 19:41:06.120574
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | Sequence[str] | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "chats",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("listing_id", sa.Uuid(), nullable=True),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("provider_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"], ["accounts.id"], name=op.f("fk_chats_customer_id_accounts")
        ),
        sa.ForeignKeyConstraint(
            ["listing_id"],
            ["listings.id"],
            name=op.f("fk_chats_listing_id_listings"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["provider_id"], ["accounts.id"], name=op.f("fk_chats_provider_id_accounts")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chats")),
        sa.UniqueConstraint(
            "listing_id", "customer_id", "provider_id", name=op.f("uq_chats_listing_id")
        ),
    )
    op.create_index(op.f("ix_chats_customer_id"), "chats", ["customer_id"], unique=False)
    op.create_index(op.f("ix_chats_listing_id"), "chats", ["listing_id"], unique=False)
    op.create_index(op.f("ix_chats_provider_id"), "chats", ["provider_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_chats_provider_id"), table_name="chats")
    op.drop_index(op.f("ix_chats_listing_id"), table_name="chats")
    op.drop_index(op.f("ix_chats_customer_id"), table_name="chats")
    op.drop_table("chats")
