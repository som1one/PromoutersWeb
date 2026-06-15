"""add_bso_file_to_orders

Revision ID: a1b2c3d4e5f6
Revises: bbb80d2da8d6
Create Date: 2025-11-18 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'bbb80d2da8d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('orders', sa.Column('bso_file_path', sa.String(length=500), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('orders', 'bso_file_path')

