"""Add branch_expenses (простые расходы филиала).

Revision ID: 0013
Revises: 0012
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "0013_branch_expenses"
down_revision = "0012_session_route_nullable"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "branch_expenses",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "branch_id",
            UUID(as_uuid=True),
            sa.ForeignKey("branches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_by_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("topic", sa.String(255), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="RUB"),
        sa.Column("receipt_path", sa.String(500), nullable=True),
        sa.Column("no_receipt", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_branch_expenses_branch_id", "branch_expenses", ["branch_id"])


def downgrade() -> None:
    op.drop_index("ix_branch_expenses_branch_id", table_name="branch_expenses")
    op.drop_table("branch_expenses")
