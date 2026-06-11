"""Add city_id to users table.

Adds ``city_id`` (nullable Integer FK → cities.id) to ``users`` so that a
master user can be assigned to a city independently of a branch.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0007_city_id_to_users"
down_revision = "0006_pj2_merge"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("city_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_users_city_id",
        "users",
        "cities",
        ["city_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_users_city_id", "users", ["city_id"])


def downgrade() -> None:
    op.drop_index("ix_users_city_id", table_name="users")
    op.drop_constraint("fk_users_city_id", "users", type_="foreignkey")
    op.drop_column("users", "city_id")
