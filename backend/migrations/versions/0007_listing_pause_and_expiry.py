"""add listing pause and expiry

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-04 14:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | Sequence[str] | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("listings", sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("listings", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
    # Existing listings get the default 30-day lifetime (FR-019) counted from publication.
    op.execute("UPDATE listings SET expires_at = created_at + interval '30 days'")
    op.alter_column("listings", "expires_at", nullable=False)
    op.create_index(op.f("ix_listings_expires_at"), "listings", ["expires_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_listings_expires_at"), table_name="listings")
    op.drop_column("listings", "expires_at")
    op.drop_column("listings", "paused_at")
