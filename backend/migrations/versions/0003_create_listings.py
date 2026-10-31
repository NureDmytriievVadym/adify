"""create listings and attachments

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-31 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "listings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "request",
                "offer",
                name="listing_type",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column(
            "category",
            sa.Enum(
                "website-banners",
                "sponsored-articles",
                "social-media-posts",
                "video-integrations",
                "stream-ads",
                "in-app-mobile-ads",
                name="listing_category",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("price", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("delivery_days", sa.Integer(), nullable=True),
        sa.Column("specs", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["accounts.id"], name=op.f("fk_listings_owner_id_accounts")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_listings")),
    )
    op.create_index(op.f("ix_listings_owner_id"), "listings", ["owner_id"], unique=False)
    op.create_table(
        "listing_attachments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("listing_id", sa.Uuid(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["listing_id"],
            ["listings.id"],
            name=op.f("fk_listing_attachments_listing_id_listings"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_listing_attachments")),
    )
    op.create_index(
        op.f("ix_listing_attachments_listing_id"),
        "listing_attachments",
        ["listing_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_listing_attachments_listing_id"), table_name="listing_attachments")
    op.drop_table("listing_attachments")
    op.drop_index(op.f("ix_listings_owner_id"), table_name="listings")
    op.drop_table("listings")
