"""Merge PythonProject2 tables: cities, equipment_types, orders, stats, attendance, penalties, system_settings.

Adds PJ2 bot-compatibility columns to ``users`` (tg_id, name, full_name, master_percentage,
passport_photo_path), creates the PJ2 service-order tables with PJ2's integer PKs/column
names exactly as declared in ``PythonProject2/model.py``, and seeds new role codes
(``director``, ``dispatcher``, ``user``).
"""

from __future__ import annotations

import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0006_pj2_merge"
down_revision = "0005_full_tz"
branch_labels = None
depends_on = None


NEW_ROLES = [
    {
        "code": "director",
        "name": "Director",
        "description": "PJ2 director role: full branch operations and finance access.",
    },
    {
        "code": "dispatcher",
        "name": "Dispatcher",
        "description": "PJ2 dispatcher role: receives client calls, creates and assigns orders.",
    },
    {
        "code": "user",
        "name": "User",
        "description": "PJ2 generic user role (legacy, narrow access).",
    },
]


def upgrade() -> None:
    bind = op.get_bind()

    # ---- users: PJ2 bridge columns ------------------------------------------
    # tg_id is BigInteger to fit full 64-bit Telegram IDs. PJ2's model.py
    # declares Integer; Python int values fit either way, and PG implicitly
    # widens on read.
    op.add_column("users", sa.Column("tg_id", sa.BigInteger(), nullable=True))
    op.add_column("users", sa.Column("name", sa.String(length=200), nullable=True))
    op.add_column("users", sa.Column("full_name", sa.String(length=200), nullable=True))
    op.add_column("users", sa.Column("master_percentage", sa.Float(), nullable=True))
    op.add_column("users", sa.Column("passport_photo_path", sa.String(length=500), nullable=True))
    op.create_unique_constraint("uq_users_tg_id", "users", ["tg_id"])
    op.create_index("ix_users_tg_id", "users", ["tg_id"])

    # ---- cities (SERIAL int PK, matches PJ2 model.py City) ------------------
    op.create_table(
        "cities",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("cash_company_percentage", sa.Float(), nullable=True, server_default="50.0"),
        sa.Column("timezone", sa.String(length=100), nullable=True, server_default="Europe/Moscow"),
        sa.UniqueConstraint("name", name="uq_cities_name"),
    )

    # ---- equipment_types ----------------------------------------------------
    op.create_table(
        "equipment_types",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("master_pct", sa.Float(), nullable=True, server_default="60.0"),
        sa.Column("company_pct", sa.Float(), nullable=True, server_default="40.0"),
        sa.UniqueConstraint("name", name="uq_equipment_types_name"),
    )

    # ---- orders -------------------------------------------------------------
    op.create_table(
        "orders",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("order_number", sa.Integer(), nullable=False),
        sa.Column("city_id", sa.Integer(), nullable=True),
        sa.Column("street", sa.String(length=500), nullable=True),
        sa.Column("house", sa.String(length=100), nullable=True),
        sa.Column("flat", sa.String(length=100), nullable=True),
        sa.Column("time_from", sa.String(length=50), nullable=True),
        sa.Column("time_to", sa.String(length=50), nullable=True),
        sa.Column("order_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("equip_type", sa.String(length=100), nullable=True),
        sa.Column("short_desc", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=200), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="new"),
        # created_by/assigned_to reference users.tg_id (BigInt). FK to users.tg_id
        # to match PJ2 model.py.
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("assigned_to", sa.BigInteger(), nullable=True),
        sa.Column("client_phone", sa.String(length=100), nullable=True),
        sa.Column("client_name", sa.String(length=200), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("sum_amount", sa.Float(), nullable=True),
        sa.Column("paid_amount", sa.Float(), nullable=True),
        sa.Column("debt_amount", sa.Float(), nullable=True),
        sa.Column("debt_payment_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sd_price", sa.Float(), nullable=True),
        sa.Column("zpch_sum", sa.Float(), nullable=True),
        sa.Column("is_warranty", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("warranty_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("warranty_days", sa.Integer(), nullable=True),
        sa.Column("warranty_source_order_id", sa.Integer(), nullable=True),
        sa.Column("receipt_file_id", sa.String(length=500), nullable=True),
        sa.Column("receipt_file_path", sa.String(length=500), nullable=True),
        sa.Column("bso_file_path", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("order_number", name="uq_orders_order_number"),
        sa.ForeignKeyConstraint(["city_id"], ["cities.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.tg_id"]),
        sa.ForeignKeyConstraint(["assigned_to"], ["users.tg_id"]),
    )
    op.create_index("ix_orders_city_id", "orders", ["city_id"])
    op.create_index("ix_orders_created_by", "orders", ["created_by"])
    op.create_index("ix_orders_assigned_to", "orders", ["assigned_to"])

    # ---- stats --------------------------------------------------------------
    op.create_table(
        "stats",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("order_id", sa.Integer(), nullable=True),
        sa.Column("equip_type", sa.String(length=100), nullable=True),
        sa.Column("sum", sa.Float(), nullable=True, server_default="0.0"),
        sa.Column("refused", sa.Boolean(), nullable=True, server_default=sa.false()),
        sa.Column("master_tg", sa.BigInteger(), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_stats_order_id", "stats", ["order_id"])
    op.create_index("ix_stats_master_tg", "stats", ["master_tg"])

    # ---- attendance ---------------------------------------------------------
    op.create_table(
        "attendance",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("master_tg_id", sa.BigInteger(), nullable=False),
        sa.Column("check_in_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_penalty", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["master_tg_id"], ["users.tg_id"]),
    )
    op.create_index("ix_attendance_master_tg_id", "attendance", ["master_tg_id"])
    op.create_index("ix_attendance_date", "attendance", ["date"])

    # ---- penalties ----------------------------------------------------------
    op.create_table(
        "penalties",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("master_tg_id", sa.BigInteger(), nullable=False),
        sa.Column("attendance_id", sa.Integer(), nullable=True),
        sa.Column("date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("amount", sa.Float(), nullable=True, server_default="0.0"),
        sa.Column(
            "reason",
            sa.String(length=500),
            nullable=True,
            server_default="Опоздание на смену (отметка не сделана до 9:00)",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["master_tg_id"], ["users.tg_id"]),
        sa.ForeignKeyConstraint(["attendance_id"], ["attendance.id"]),
    )
    op.create_index("ix_penalties_master_tg_id", "penalties", ["master_tg_id"])

    # ---- system_settings ----------------------------------------------------
    op.create_table(
        "system_settings",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", sa.String(length=500), nullable=True),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("key", name="uq_system_settings_key"),
    )
    op.create_index("ix_system_settings_key", "system_settings", ["key"])

    # ---- seed new role codes (director / dispatcher / user) -----------------
    roles_table = sa.table(
        "roles",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
        sa.column("description", sa.Text()),
        sa.column("is_system", sa.Boolean()),
    )

    existing_codes = {
        row[0]
        for row in bind.execute(sa.text("SELECT code FROM roles WHERE code IS NOT NULL"))
    }

    new_rows = []
    for role in NEW_ROLES:
        if role["code"] in existing_codes:
            continue
        new_rows.append(
            {
                "id": uuid.uuid4(),
                "code": role["code"],
                "name": role["name"],
                "description": role["description"],
                "is_system": True,
            }
        )
    if new_rows:
        op.bulk_insert(roles_table, new_rows)


def downgrade() -> None:
    bind = op.get_bind()

    # Remove seeded roles (only if no users reference them)
    bind.execute(
        sa.text(
            "DELETE FROM roles WHERE code IN ('director','dispatcher','user') "
            "AND id NOT IN (SELECT DISTINCT role_id FROM users WHERE role_id IS NOT NULL)"
        )
    )

    op.drop_index("ix_system_settings_key", table_name="system_settings")
    op.drop_table("system_settings")

    op.drop_index("ix_penalties_master_tg_id", table_name="penalties")
    op.drop_table("penalties")

    op.drop_index("ix_attendance_date", table_name="attendance")
    op.drop_index("ix_attendance_master_tg_id", table_name="attendance")
    op.drop_table("attendance")

    op.drop_index("ix_stats_master_tg", table_name="stats")
    op.drop_index("ix_stats_order_id", table_name="stats")
    op.drop_table("stats")

    op.drop_index("ix_orders_assigned_to", table_name="orders")
    op.drop_index("ix_orders_created_by", table_name="orders")
    op.drop_index("ix_orders_city_id", table_name="orders")
    op.drop_table("orders")

    op.drop_table("equipment_types")
    op.drop_table("cities")

    op.drop_index("ix_users_tg_id", table_name="users")
    op.drop_constraint("uq_users_tg_id", "users", type_="unique")
    op.drop_column("users", "passport_photo_path")
    op.drop_column("users", "master_percentage")
    op.drop_column("users", "full_name")
    op.drop_column("users", "name")
    op.drop_column("users", "tg_id")
