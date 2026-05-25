"""Add payout calculation details JSON field."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004_payout_calc"
down_revision = "0003_role_scope"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("payouts", sa.Column("calculation_details", postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column("payouts", "calculation_details")
