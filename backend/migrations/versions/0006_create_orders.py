"""create orders

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-04 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "orders",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("listing_id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("provider_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "in_progress",
                "completed",
                "cancelled",
                "disputed",
                name="order_status",
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
        sa.ForeignKeyConstraint(
            ["listing_id"], ["listings.id"], name=op.f("fk_orders_listing_id_listings")
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"], ["accounts.id"], name=op.f("fk_orders_customer_id_accounts")
        ),
        sa.ForeignKeyConstraint(
            ["provider_id"], ["accounts.id"], name=op.f("fk_orders_provider_id_accounts")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_orders")),
    )
    op.create_index(op.f("ix_orders_listing_id"), "orders", ["listing_id"], unique=False)
    op.create_index(op.f("ix_orders_customer_id"), "orders", ["customer_id"], unique=False)
    op.create_index(op.f("ix_orders_provider_id"), "orders", ["provider_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_orders_provider_id"), table_name="orders")
    op.drop_index(op.f("ix_orders_customer_id"), table_name="orders")
    op.drop_index(op.f("ix_orders_listing_id"), table_name="orders")
    op.drop_table("orders")
