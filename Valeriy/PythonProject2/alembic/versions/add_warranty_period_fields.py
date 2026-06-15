"""add_warranty_period_fields

Revision ID: add_warranty_period_001
Revises: add_debt_fields_001
Create Date: 2025-12-19 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "add_warranty_period_001"
down_revision: Union[str, Sequence[str], None] = "add_debt_fields_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("warranty_until", sa.DateTime(timezone=True), nullable=True))
    op.add_column("orders", sa.Column("warranty_days", sa.Integer(), nullable=True))
    op.add_column("orders", sa.Column("warranty_source_order_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "warranty_source_order_id")
    op.drop_column("orders", "warranty_days")
    op.drop_column("orders", "warranty_until")


