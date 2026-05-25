"""Add login SMS code challenges."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_sms_codes"
down_revision = "0001_init"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "login_sms_codes",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=False),
        sa.Column("code_hash", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invalid_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_login_sms_codes_user_id", "login_sms_codes", ["user_id"])
    op.create_index("ix_login_sms_codes_phone", "login_sms_codes", ["phone"])
    op.create_index("ix_login_sms_codes_expires_at", "login_sms_codes", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_login_sms_codes_expires_at", table_name="login_sms_codes")
    op.drop_index("ix_login_sms_codes_phone", table_name="login_sms_codes")
    op.drop_index("ix_login_sms_codes_user_id", table_name="login_sms_codes")
    op.drop_table("login_sms_codes")
