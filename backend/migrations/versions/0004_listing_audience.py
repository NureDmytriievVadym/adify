"""add listing target audience

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-01 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("listings", sa.Column("audience_age_min", sa.Integer(), nullable=True))
    op.add_column("listings", sa.Column("audience_age_max", sa.Integer(), nullable=True))
    op.add_column("listings", sa.Column("audience_country", sa.String(length=100), nullable=True))
    op.add_column(
        "listings", sa.Column("audience_socioeconomic", sa.String(length=100), nullable=True)
    )
    op.add_column(
        "listings",
        sa.Column("audience_traits", sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("listings", "audience_traits")
    op.drop_column("listings", "audience_socioeconomic")
    op.drop_column("listings", "audience_country")
    op.drop_column("listings", "audience_age_max")
    op.drop_column("listings", "audience_age_min")
