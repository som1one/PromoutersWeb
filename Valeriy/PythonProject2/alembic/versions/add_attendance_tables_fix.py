"""add_attendance_tables_fix

Revision ID: add_attendance_fix_001
Revises: add_is_warranty_001
Create Date: 2025-11-09 14:25:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import func


# revision identifiers, used by Alembic.
revision: str = "add_attendance_fix_001"
down_revision: Union[str, Sequence[str], None] = "add_is_warranty_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "attendance" not in inspector.get_table_names():
        op.create_table(
            "attendance",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("master_tg_id", sa.Integer(), sa.ForeignKey("users.tg_id"), nullable=False),
            sa.Column("check_in_time", sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
            sa.Column("date", sa.DateTime(timezone=True), nullable=False),
            sa.Column("is_penalty", sa.Boolean(), server_default=sa.text("false"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
        )

    if "penalties" not in inspector.get_table_names():
        op.create_table(
            "penalties",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("master_tg_id", sa.Integer(), sa.ForeignKey("users.tg_id"), nullable=False),
            sa.Column("attendance_id", sa.Integer(), sa.ForeignKey("attendance.id"), nullable=True),
            sa.Column("date", sa.DateTime(timezone=True), nullable=False),
            sa.Column("amount", sa.Float(), server_default=sa.text("0"), nullable=False),
            sa.Column("reason", sa.String(length=500), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "penalties" in inspector.get_table_names():
        op.drop_table("penalties")
    if "attendance" in inspector.get_table_names():
        op.drop_table("attendance")


