"""Add master cabinet, promoter report review, expense plan items, route map image."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0005_full_tz"
down_revision = "0004_payout_calc"
branch_labels = None
depends_on = None


promoter_report_review_status_enum = postgresql.ENUM(
    "pending",
    "accepted_by_director",
    "forwarded_to_manager",
    "rejected",
    name="promoter_report_review_status_enum",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()

    # ---- master_requests: новые статусы и поля -------------------------------------------------
    op.execute("ALTER TYPE master_request_status_enum ADD VALUE IF NOT EXISTS 'cancelled'")

    op.add_column("master_requests", sa.Column("address", sa.String(length=255), nullable=True))
    op.add_column("master_requests", sa.Column("client_name", sa.String(length=255), nullable=True))
    op.add_column("master_requests", sa.Column("client_phone", sa.String(length=64), nullable=True))
    op.add_column("master_requests", sa.Column("estimated_amount", sa.Numeric(12, 2), nullable=True))
    op.add_column("master_requests", sa.Column("final_amount", sa.Numeric(12, 2), nullable=True))
    op.add_column(
        "master_requests",
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="RUB"),
    )
    op.add_column("master_requests", sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("master_requests", sa.Column("handed_over_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("master_requests", sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("master_requests", sa.Column("last_known_latitude", sa.Numeric(10, 7), nullable=True))
    op.add_column("master_requests", sa.Column("last_known_longitude", sa.Numeric(10, 7), nullable=True))
    op.add_column("master_requests", sa.Column("last_known_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "master_request_comments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("master_request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["master_request_id"], ["master_requests.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index(
        "ix_master_request_comments_master_request_id",
        "master_request_comments",
        ["master_request_id"],
    )

    op.create_table(
        "master_request_status_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("master_request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("changed_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "from_status",
            postgresql.ENUM(name="master_request_status_enum", create_type=False),
            nullable=True,
        ),
        sa.Column(
            "to_status",
            postgresql.ENUM(name="master_request_status_enum", create_type=False),
            nullable=False,
        ),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["master_request_id"], ["master_requests.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["changed_by_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "ix_master_request_status_logs_master_request_id",
        "master_request_status_logs",
        ["master_request_id"],
    )

    op.create_table(
        "master_geo_pings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("master_request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("master_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("latitude", sa.Numeric(10, 7), nullable=False),
        sa.Column("longitude", sa.Numeric(10, 7), nullable=False),
        sa.Column("accuracy_meters", sa.Numeric(10, 2), nullable=True),
        sa.Column(
            "status_at_capture",
            postgresql.ENUM(name="master_request_status_enum", create_type=False),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["master_request_id"], ["master_requests.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["master_id"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index(
        "ix_master_geo_pings_master_request_id",
        "master_geo_pings",
        ["master_request_id"],
    )

    # ---- expense_plans: title, items table -----------------------------------------------------
    op.add_column(
        "expense_plans",
        sa.Column("title", sa.String(length=255), nullable=False, server_default="План расходов"),
    )

    op.create_table(
        "expense_plan_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("expense_plan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("quantity", sa.Numeric(12, 2), nullable=False, server_default="1"),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["expense_plan_id"], ["expense_plans.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_expense_plan_items_expense_plan_id",
        "expense_plan_items",
        ["expense_plan_id"],
    )

    # ---- promoter_sessions: review workflow ----------------------------------------------------
    promoter_report_review_status_enum.create(bind, checkfirst=True)

    op.add_column(
        "promoter_sessions",
        sa.Column(
            "review_status",
            postgresql.ENUM(
                name="promoter_report_review_status_enum", create_type=False
            ),
            nullable=False,
            server_default="pending",
        ),
    )
    op.add_column("promoter_sessions", sa.Column("review_comment", sa.Text(), nullable=True))
    op.add_column(
        "promoter_sessions",
        sa.Column("accepted_by_director_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "promoter_sessions",
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "promoter_sessions",
        sa.Column("forwarded_by_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "promoter_sessions",
        sa.Column("forwarded_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_promoter_sessions_accepted_by_director",
        "promoter_sessions",
        "users",
        ["accepted_by_director_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_promoter_sessions_forwarded_by",
        "promoter_sessions",
        "users",
        ["forwarded_by_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # ---- routes: map_image_path ----------------------------------------------------------------
    op.add_column("routes", sa.Column("map_image_path", sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column("routes", "map_image_path")

    op.drop_constraint("fk_promoter_sessions_forwarded_by", "promoter_sessions", type_="foreignkey")
    op.drop_constraint("fk_promoter_sessions_accepted_by_director", "promoter_sessions", type_="foreignkey")
    op.drop_column("promoter_sessions", "forwarded_at")
    op.drop_column("promoter_sessions", "forwarded_by_id")
    op.drop_column("promoter_sessions", "accepted_at")
    op.drop_column("promoter_sessions", "accepted_by_director_id")
    op.drop_column("promoter_sessions", "review_comment")
    op.drop_column("promoter_sessions", "review_status")

    bind = op.get_bind()
    promoter_report_review_status_enum.drop(bind, checkfirst=True)

    op.drop_index("ix_expense_plan_items_expense_plan_id", table_name="expense_plan_items")
    op.drop_table("expense_plan_items")
    op.drop_column("expense_plans", "title")

    op.drop_index("ix_master_geo_pings_master_request_id", table_name="master_geo_pings")
    op.drop_table("master_geo_pings")

    op.drop_index("ix_master_request_status_logs_master_request_id", table_name="master_request_status_logs")
    op.drop_table("master_request_status_logs")

    op.drop_index("ix_master_request_comments_master_request_id", table_name="master_request_comments")
    op.drop_table("master_request_comments")

    op.drop_column("master_requests", "last_known_at")
    op.drop_column("master_requests", "last_known_longitude")
    op.drop_column("master_requests", "last_known_latitude")
    op.drop_column("master_requests", "cancelled_at")
    op.drop_column("master_requests", "handed_over_at")
    op.drop_column("master_requests", "accepted_at")
    op.drop_column("master_requests", "currency")
    op.drop_column("master_requests", "final_amount")
    op.drop_column("master_requests", "estimated_amount")
    op.drop_column("master_requests", "client_phone")
    op.drop_column("master_requests", "client_name")
    op.drop_column("master_requests", "address")
