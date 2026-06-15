"""add_zpch_sum_to_orders

Revision ID: add_zpch_sum_001
Revises: add_sd_price_001
Create Date: 2025-11-01 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_zpch_sum_001'
down_revision: Union[str, Sequence[str], None] = 'add_sd_price_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('orders', sa.Column('zpch_sum', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('orders', 'zpch_sum')


