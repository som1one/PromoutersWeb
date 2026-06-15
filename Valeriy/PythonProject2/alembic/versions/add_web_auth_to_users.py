"""add_web_auth_to_users

Revision ID: add_web_auth_001
Revises: f7a99a334367
Create Date: 2025-01-15 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_web_auth_001'
# Оставляем исходную зависимость, так как миграция уже применена на сервере
# Merge-миграция объединит эту ветку с основной
down_revision: Union[str, Sequence[str], None] = 'f7a99a334367'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Добавляем поля для веб-аутентификации
    op.add_column('users', sa.Column('username', sa.String(length=100), nullable=True))
    op.add_column('users', sa.Column('password_hash', sa.String(length=255), nullable=True))
    
    # Создаем уникальный индекс для username
    op.create_index('ix_users_username', 'users', ['username'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    # Удаляем индекс
    op.drop_index('ix_users_username', table_name='users')
    
    # Удаляем колонки
    op.drop_column('users', 'password_hash')
    op.drop_column('users', 'username')

