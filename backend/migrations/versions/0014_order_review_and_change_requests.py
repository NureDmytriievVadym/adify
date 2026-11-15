"""order review and change requests

Revision ID: 0014
Revises: 0013
Create Date: 2026-11-14 14:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: str | Sequence[str] | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("review_started_at", sa.DateTime(timezone=True)))
    op.add_column("orders", sa.Column("completed_at", sa.DateTime(timezone=True)))
    op.create_table(
        "order_change_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "agreed",
                "declined",
                "withdrawn",
                name="change_request_status",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_order_change_requests_order_id_orders"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_order_change_requests")),
    )
    op.create_index(
        op.f("ix_order_change_requests_order_id"),
        "order_change_requests",
        ["order_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_order_change_requests_order_id"), table_name="order_change_requests")
    op.drop_table("order_change_requests")
    op.drop_column("orders", "completed_at")
    op.drop_column("orders", "review_started_at")
