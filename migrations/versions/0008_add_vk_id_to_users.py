"""Add vk_id to users table.

Adds ``vk_id`` (nullable String(100), unique, indexed) to ``users``
for VK social network identification alongside existing tg_id.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0008_add_vk_id"
down_revision = "0007_city_id_to_users"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("vk_id", sa.String(100), nullable=True),
    )
    op.create_unique_constraint("uq_users_vk_id", "users", ["vk_id"])
    op.create_index("ix_users_vk_id", "users", ["vk_id"])


def downgrade() -> None:
    op.drop_index("ix_users_vk_id", table_name="users")
    op.drop_constraint("uq_users_vk_id", "users", type_="unique")
    op.drop_column("users", "vk_id")
