"""order details stages and snapshot

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-10 12:57:23.932462
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | Sequence[str] | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


OLD_STATES = ("pending", "in_progress", "completed", "cancelled", "disputed")
NEW_STATES = (
    "awaiting_payment",
    "paid",
    "in_progress",
    "in_review",
    "disputed",
    "done",
    "canceled",
    "rejected",
)
RENAMES = {"pending": "awaiting_payment", "completed": "done", "cancelled": "canceled"}


def _rename(mapping: dict[str, str]) -> None:
    for old, new in mapping.items():
        op.execute(
            sa.text("UPDATE orders SET status = :new WHERE status = :old").bindparams(
                new=new, old=old
            )
        )


def upgrade() -> None:
    op.create_table(
        "order_stages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("deadline", sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_order_stages_order_id_orders"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_order_stages")),
    )
    op.create_index(op.f("ix_order_stages_order_id"), "order_stages", ["order_id"], unique=False)

    # SRS §3.4.4 names the order states; existing rows keep their meaning.
    op.drop_constraint(op.f("ck_orders_order_status"), "orders", type_="check")
    _rename(RENAMES)
    listed = ", ".join(f"'{state}'" for state in NEW_STATES)
    op.create_check_constraint(op.f("ck_orders_order_status"), "orders", f"status IN ({listed})")

    op.add_column("orders", sa.Column("chat_id", sa.Uuid(), nullable=True))
    op.add_column("orders", sa.Column("owner_id", sa.Uuid(), nullable=True))
    op.add_column("orders", sa.Column("details", sa.Text(), nullable=False, server_default=""))
    op.add_column("orders", sa.Column("price", sa.Numeric(precision=10, scale=2), nullable=True))
    op.add_column("orders", sa.Column("deadline", sa.Date(), nullable=True))
    op.add_column("orders", sa.Column("requirements", sa.JSON(), nullable=True))
    # Orders created before this story (only the demo order) take their listing's values.
    op.execute(
        """
        UPDATE orders SET
            owner_id = listings.owner_id,
            price = listings.price,
            requirements = json_build_object(
                'listing_type', listings.type,
                'category', listings.category,
                'has_requirements', json_array_length(listings.specs) > 0,
                'specs', listings.specs
            )
        FROM listings WHERE listings.id = orders.listing_id
        """
    )
    op.alter_column("orders", "owner_id", nullable=False)
    op.alter_column("orders", "price", nullable=False)
    op.alter_column("orders", "requirements", nullable=False)
    op.alter_column("orders", "details", server_default=None)
    op.create_index(op.f("ix_orders_chat_id"), "orders", ["chat_id"], unique=False)
    op.create_index(op.f("ix_orders_owner_id"), "orders", ["owner_id"], unique=False)
    op.create_foreign_key(
        op.f("fk_orders_chat_id_chats"), "orders", "chats", ["chat_id"], ["id"], ondelete="SET NULL"
    )
    op.create_foreign_key(
        op.f("fk_orders_owner_id_accounts"), "orders", "accounts", ["owner_id"], ["id"]
    )


def downgrade() -> None:
    op.drop_constraint(op.f("fk_orders_owner_id_accounts"), "orders", type_="foreignkey")
    op.drop_constraint(op.f("fk_orders_chat_id_chats"), "orders", type_="foreignkey")
    op.drop_index(op.f("ix_orders_owner_id"), table_name="orders")
    op.drop_index(op.f("ix_orders_chat_id"), table_name="orders")
    op.drop_column("orders", "requirements")
    op.drop_column("orders", "deadline")
    op.drop_column("orders", "price")
    op.drop_column("orders", "details")
    op.drop_column("orders", "owner_id")
    op.drop_column("orders", "chat_id")

    op.drop_constraint(op.f("ck_orders_order_status"), "orders", type_="check")
    # States with no earlier equivalent fall back to the closest old one.
    _rename(
        {v: k for k, v in RENAMES.items()}
        | {"paid": "pending", "in_review": "in_progress", "rejected": "cancelled"}
    )
    listed = ", ".join(f"'{state}'" for state in OLD_STATES)
    op.create_check_constraint(op.f("ck_orders_order_status"), "orders", f"status IN ({listed})")

    op.drop_index(op.f("ix_order_stages_order_id"), table_name="order_stages")
    op.drop_table("order_stages")
