"""add_review_fields_comments_avito_profile

Revision ID: 51cff790aa95
Revises: c5a4776817fd
Create Date: 2025-11-07 21:52:37.435350

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '51cff790aa95'
down_revision: Union[str, Sequence[str], None] = 'c5a4776817fd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
