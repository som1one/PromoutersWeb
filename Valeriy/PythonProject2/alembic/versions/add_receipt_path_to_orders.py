"""add_receipt_path_to_orders

Revision ID: add_receipt_path_001
Revises: add_attendance_fix_001
Create Date: 2025-11-09 14:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "add_receipt_path_001"
down_revision: Union[str, Sequence[str], None] = "add_attendance_fix_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("receipt_file_path", sa.String(length=500), nullable=True))
    op.add_column("cities", sa.Column("timezone", sa.String(length=100), nullable=True))
    op.execute("UPDATE cities SET timezone = 'Europe/Moscow' WHERE timezone IS NULL")
    op.alter_column(
        "cities",
        "timezone",
        nullable=False,
        server_default="Europe/Moscow",
        existing_type=sa.String(length=100),
    )


def downgrade() -> None:
    op.drop_column("orders", "receipt_file_path")
    op.drop_column("cities", "timezone")


