"""Make promoter_sessions.route_id nullable for route-free shifts.

Promoters can now start shifts via VK bot without a pre-created route.
The session tracks time independently.
"""

from alembic import op
import sqlalchemy as sa


revision = "0012_session_route_nullable"
down_revision = "0011_promoter_payment_details"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "promoter_sessions",
        "route_id",
        existing_type=sa.String(36),
        nullable=True,
    )


def downgrade() -> None:
    # Delete sessions without routes before making NOT NULL again
    op.execute("DELETE FROM promoter_sessions WHERE route_id IS NULL")
    op.alter_column(
        "promoter_sessions",
        "route_id",
        existing_type=sa.String(36),
        nullable=False,
    )
