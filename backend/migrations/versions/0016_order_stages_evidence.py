"""order stages and evidence

Revision ID: 0016
Revises: 0015
Create Date: 2026-11-14 17:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: str | Sequence[str] | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("order_stages", sa.Column("completed_at", sa.DateTime(timezone=True)))
    op.add_column("order_stages", sa.Column("completed_by_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f("fk_order_stages_completed_by_id_accounts"),
        "order_stages",
        "accounts",
        ["completed_by_id"],
        ["id"],
    )

    op.create_table(
        "order_evidence",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_order_evidence_order_id_orders"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["author_id"],
            ["accounts.id"],
            name=op.f("fk_order_evidence_author_id_accounts"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_order_evidence")),
    )
    op.create_index(
        op.f("ix_order_evidence_order_id"), "order_evidence", ["order_id"], unique=False
    )
    op.create_index(
        op.f("ix_order_evidence_author_id"), "order_evidence", ["author_id"], unique=False
    )

    op.create_table(
        "order_evidence_files",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("evidence_id", sa.Uuid(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column(
            "scan_result",
            sa.String(length=20),
            nullable=False,
            server_default="clean",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["evidence_id"],
            ["order_evidence.id"],
            name=op.f("fk_order_evidence_files_evidence_id_order_evidence"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_order_evidence_files")),
    )
    op.create_index(
        op.f("ix_order_evidence_files_evidence_id"),
        "order_evidence_files",
        ["evidence_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_order_evidence_files_evidence_id"), table_name="order_evidence_files")
    op.drop_table("order_evidence_files")
    op.drop_index(op.f("ix_order_evidence_author_id"), table_name="order_evidence")
    op.drop_index(op.f("ix_order_evidence_order_id"), table_name="order_evidence")
    op.drop_table("order_evidence")
    op.drop_constraint(
        op.f("fk_order_stages_completed_by_id_accounts"), "order_stages", type_="foreignkey"
    )
    op.drop_column("order_stages", "completed_by_id")
    op.drop_column("order_stages", "completed_at")
