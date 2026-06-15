"""add_debt_fields_to_orders

Revision ID: add_debt_fields_001
Revises: 21c200b24705, add_web_auth_001
Create Date: 2025-01-27 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_debt_fields_001'
# Зависит от обеих голов - это объединит ветки и добавит поля
down_revision: Union[str, Sequence[str], None] = ['21c200b24705', 'add_web_auth_001']
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Добавляем поля для отслеживания долгов
    op.add_column('orders', sa.Column('paid_amount', sa.Float(), nullable=True))
    op.add_column('orders', sa.Column('debt_amount', sa.Float(), nullable=True))
    op.add_column('orders', sa.Column('debt_payment_date', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # Удаляем поля долгов
    op.drop_column('orders', 'debt_payment_date')
    op.drop_column('orders', 'debt_amount')
    op.drop_column('orders', 'paid_amount')

