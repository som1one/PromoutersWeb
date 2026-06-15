"""add_is_warranty_to_orders

Revision ID: add_is_warranty_001
Revises: c5a4776817fd
Create Date: 2025-11-07 21:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "add_is_warranty_001"
down_revision: Union[str, Sequence[str], None] = "51cff790aa95"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column("is_warranty", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("orders", "is_warranty")


