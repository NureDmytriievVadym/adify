"""order work start and cancellation

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-14 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | Sequence[str] | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("work_started_at", sa.DateTime(timezone=True)))
    op.add_column("orders", sa.Column("canceled_at", sa.DateTime(timezone=True)))
    op.add_column("orders", sa.Column("cancel_reason", sa.String(length=40)))


def downgrade() -> None:
    op.drop_column("orders", "cancel_reason")
    op.drop_column("orders", "canceled_at")
    op.drop_column("orders", "work_started_at")
