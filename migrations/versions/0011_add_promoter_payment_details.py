"""Add promoter payment details and payment proof screenshot.

Revision ID: 0011
Revises: 0010
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "0011_promoter_payment_details"
down_revision = "0010_payout_route_nullable"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Promoter payment details (bank requisites)
    op.create_table(
        "promoter_payment_details",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("phone_number", sa.String(32), nullable=False),
        sa.Column("bank_name", sa.String(128), nullable=False),
        sa.Column("card_holder_name", sa.String(200), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_promoter_payment_details_user_id", "promoter_payment_details", ["user_id"])

    # Payment proof screenshot on payouts
    op.add_column("payouts", sa.Column("payment_proof_path", sa.String(500), nullable=True))
    op.add_column("payouts", sa.Column("paid_by_id", UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_payouts_paid_by_id_users",
        "payouts", "users",
        ["paid_by_id"], ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_payouts_paid_by_id_users", "payouts", type_="foreignkey")
    op.drop_column("payouts", "paid_by_id")
    op.drop_column("payouts", "payment_proof_path")
    op.drop_index("ix_promoter_payment_details_user_id", table_name="promoter_payment_details")
    op.drop_table("promoter_payment_details")
