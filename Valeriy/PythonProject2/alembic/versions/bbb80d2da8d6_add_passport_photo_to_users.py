"""add_passport_photo_to_users

Revision ID: bbb80d2da8d6
Revises: 47d580f2bd85
Create Date: 2025-11-18 00:03:21.346453

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bbb80d2da8d6'
down_revision: Union[str, Sequence[str], None] = '47d580f2bd85'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('passport_photo_path', sa.String(length=500), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'passport_photo_path')
