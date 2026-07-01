"""Make payouts.route_id nullable for manual settlements.

Manual settlements (payouts) are created without an associated route,
so route_id must be nullable.
"""

from alembic import op
import sqlalchemy as sa


revision = "0010_payout_route_nullable"
down_revision = "0009_role_col_pj2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("payouts", "route_id", existing_type=sa.String(), nullable=True)


def downgrade() -> None:
    # Remove any manual payouts (route_id IS NULL) before making column NOT NULL
    op.execute("DELETE FROM payouts WHERE route_id IS NULL")
    op.alter_column("payouts", "route_id", existing_type=sa.String(), nullable=False)
