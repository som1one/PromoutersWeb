"""Initial schema for promouters backend."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None


user_status_enum = postgresql.ENUM("active", "inactive", "suspended", name="user_status_enum", create_type=False)
route_status_enum = postgresql.ENUM(
    "draft", "assigned", "in_progress", "completed", "cancelled", name="route_status_enum", create_type=False
)
route_point_type_enum = postgresql.ENUM(
    "start", "checkpoint", "stop", "finish", name="route_point_type_enum", create_type=False
)
promoter_session_status_enum = postgresql.ENUM(
    "planned",
    "active",
    "paused",
    "completed",
    "cancelled",
    name="promoter_session_status_enum",
    create_type=False,
)
geo_ping_source_enum = postgresql.ENUM(
    "start", "tracking", "finish", "photo", "manual", name="geo_ping_source_enum", create_type=False
)
photo_report_status_enum = postgresql.ENUM(
    "pending", "accepted", "rejected", name="photo_report_status_enum", create_type=False
)
payout_rate_type_enum = postgresql.ENUM(
    "hourly", "per_leaflet", "fixed_shift", name="payout_rate_type_enum", create_type=False
)
payout_status_enum = postgresql.ENUM(
    "draft", "calculated", "approved", "paid", "cancelled", name="payout_status_enum", create_type=False
)
notification_channel_enum = postgresql.ENUM(
    "in_app", "email", "sms", "telegram", "push", name="notification_channel_enum", create_type=False
)
notification_status_enum = postgresql.ENUM(
    "pending", "sent", "read", "failed", name="notification_status_enum", create_type=False
)
expense_plan_status_enum = postgresql.ENUM(
    "draft", "submitted", "approved", "rejected", "cancelled", name="expense_plan_status_enum", create_type=False
)
expense_approval_decision_enum = postgresql.ENUM(
    "pending",
    "approved",
    "rejected",
    "needs_revision",
    name="expense_approval_decision_enum",
    create_type=False,
)
master_request_status_enum = postgresql.ENUM(
    "new",
    "accepted",
    "on_the_way",
    "in_progress",
    "completed",
    "handed_over",
    name="master_request_status_enum",
    create_type=False,
)
attachment_type_enum = postgresql.ENUM("bso", "contract", "photo", "other", name="attachment_type_enum", create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    enums = [
        user_status_enum,
        route_status_enum,
        route_point_type_enum,
        promoter_session_status_enum,
        geo_ping_source_enum,
        photo_report_status_enum,
        payout_rate_type_enum,
        payout_status_enum,
        notification_channel_enum,
        notification_status_enum,
        expense_plan_status_enum,
        expense_approval_decision_enum,
        master_request_status_enum,
        attachment_type_enum,
    ]
    for enum in enums:
        enum.create(bind, checkfirst=True)

    op.create_table(
        "roles",
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "branches",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=True),
        sa.Column("city", sa.String(length=128), nullable=True),
        sa.Column("address", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )

    op.create_table(
        "users",
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=False),
        sa.Column("middle_name", sa.String(length=100), nullable=True),
        sa.Column("status", user_status_enum, nullable=False, server_default="active"),
        sa.Column("is_superuser", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("phone"),
        sa.UniqueConstraint("username"),
    )
    op.create_index("ix_users_role_id", "users", ["role_id"])
    op.create_index("ix_users_branch_id", "users", ["branch_id"])

    op.create_table(
        "payout_rates",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("rate_type", payout_rate_type_enum, nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="RUB"),
        sa.Column("per_unit_name", sa.String(length=50), nullable=True),
        sa.Column("active_from", sa.Date(), nullable=True),
        sa.Column("active_to", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_payout_rates_branch_id", "payout_rates", ["branch_id"])
    op.create_index("ix_payout_rates_role_id", "payout_rates", ["role_id"])
    op.create_index("ix_payout_rates_created_by_id", "payout_rates", ["created_by_id"])

    op.create_table(
        "expense_plans",
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("total_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="RUB"),
        sa.Column("status", expense_plan_status_enum, nullable=False, server_default="draft"),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_expense_plans_branch_id", "expense_plans", ["branch_id"])
    op.create_index("ix_expense_plans_created_by_id", "expense_plans", ["created_by_id"])

    op.create_table(
        "routes",
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("planned_start_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("planned_end_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", route_status_enum, nullable=False, server_default="draft"),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("promoter_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payout_rate_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["payout_rate_id"], ["payout_rates.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["promoter_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_routes_branch_id", "routes", ["branch_id"])
    op.create_index("ix_routes_promoter_id", "routes", ["promoter_id"])
    op.create_index("ix_routes_created_by_id", "routes", ["created_by_id"])
    op.create_index("ix_routes_payout_rate_id", "routes", ["payout_rate_id"])
    op.create_index("ix_routes_work_date", "routes", ["work_date"])

    op.create_table(
        "master_requests",
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requester_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assignee_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", master_request_status_enum, nullable=False, server_default="new"),
        sa.Column("geo_tracking_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["assignee_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requester_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_master_requests_branch_id", "master_requests", ["branch_id"])
    op.create_index("ix_master_requests_requester_id", "master_requests", ["requester_id"])
    op.create_index("ix_master_requests_assignee_id", "master_requests", ["assignee_id"])

    op.create_table(
        "route_points",
        sa.Column("route_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("address", sa.String(length=255), nullable=True),
        sa.Column("latitude", sa.Numeric(10, 7), nullable=True),
        sa.Column("longitude", sa.Numeric(10, 7), nullable=True),
        sa.Column("point_type", route_point_type_enum, nullable=False, server_default="checkpoint"),
        sa.Column("planned_arrival_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["route_id"], ["routes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("route_id", "sequence", name="uq_route_points_route_sequence"),
    )
    op.create_index("ix_route_points_route_id", "route_points", ["route_id"])

    op.create_table(
        "promoter_sessions",
        sa.Column("route_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("promoter_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", promoter_session_status_enum, nullable=False, server_default="planned"),
        sa.Column("total_minutes", sa.Integer(), nullable=True),
        sa.Column("leaflet_count", sa.Integer(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("started_latitude", sa.Numeric(10, 7), nullable=True),
        sa.Column("started_longitude", sa.Numeric(10, 7), nullable=True),
        sa.Column("finished_latitude", sa.Numeric(10, 7), nullable=True),
        sa.Column("finished_longitude", sa.Numeric(10, 7), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["promoter_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["route_id"], ["routes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_promoter_sessions_route_id", "promoter_sessions", ["route_id"])
    op.create_index("ix_promoter_sessions_promoter_id", "promoter_sessions", ["promoter_id"])

    op.create_table(
        "expense_approvals",
        sa.Column("expense_plan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("approver_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("decision", expense_approval_decision_enum, nullable=False, server_default="pending"),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["approver_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["expense_plan_id"], ["expense_plans.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_expense_approvals_expense_plan_id", "expense_approvals", ["expense_plan_id"])
    op.create_index("ix_expense_approvals_approver_id", "expense_approvals", ["approver_id"])

    op.create_table(
        "geo_pings",
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("route_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("promoter_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("point_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("latitude", sa.Numeric(10, 7), nullable=False),
        sa.Column("longitude", sa.Numeric(10, 7), nullable=False),
        sa.Column("accuracy_meters", sa.Numeric(10, 2), nullable=True),
        sa.Column("speed_mps", sa.Numeric(10, 2), nullable=True),
        sa.Column("heading_degrees", sa.Numeric(10, 2), nullable=True),
        sa.Column("source", geo_ping_source_enum, nullable=False, server_default="tracking"),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["point_id"], ["route_points.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["promoter_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["route_id"], ["routes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["promoter_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_geo_pings_session_id", "geo_pings", ["session_id"])
    op.create_index("ix_geo_pings_route_id", "geo_pings", ["route_id"])
    op.create_index("ix_geo_pings_promoter_id", "geo_pings", ["promoter_id"])
    op.create_index("ix_geo_pings_point_id", "geo_pings", ["point_id"])
    op.create_index("ix_geo_pings_captured_at", "geo_pings", ["captured_at"])

    op.create_table(
        "photo_reports",
        sa.Column("route_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("promoter_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("point_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("thumbnail_path", sa.String(length=500), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("latitude", sa.Numeric(10, 7), nullable=True),
        sa.Column("longitude", sa.Numeric(10, 7), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", photo_report_status_enum, nullable=False, server_default="pending"),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["point_id"], ["route_points.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["promoter_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reviewed_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["route_id"], ["routes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["promoter_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_photo_reports_route_id", "photo_reports", ["route_id"])
    op.create_index("ix_photo_reports_session_id", "photo_reports", ["session_id"])
    op.create_index("ix_photo_reports_promoter_id", "photo_reports", ["promoter_id"])
    op.create_index("ix_photo_reports_point_id", "photo_reports", ["point_id"])
    op.create_index("ix_photo_reports_reviewed_by_id", "photo_reports", ["reviewed_by_id"])

    op.create_table(
        "payouts",
        sa.Column("route_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("promoter_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payout_rate_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approved_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="RUB"),
        sa.Column("units", sa.Numeric(12, 2), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", payout_status_enum, nullable=False, server_default="draft"),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["approved_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["payout_rate_id"], ["payout_rates.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["promoter_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["route_id"], ["routes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["promoter_sessions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_payouts_route_id", "payouts", ["route_id"])
    op.create_index("ix_payouts_session_id", "payouts", ["session_id"])
    op.create_index("ix_payouts_promoter_id", "payouts", ["promoter_id"])
    op.create_index("ix_payouts_payout_rate_id", "payouts", ["payout_rate_id"])
    op.create_index("ix_payouts_approved_by_id", "payouts", ["approved_by_id"])

    op.create_table(
        "audit_logs",
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("entity_type", sa.String(length=100), nullable=False),
        sa.Column("entity_id", sa.String(length=36), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_actor_user_id", "audit_logs", ["actor_user_id"])
    op.create_index("ix_audit_logs_entity_type", "audit_logs", ["entity_type"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])

    op.create_table(
        "notifications",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("channel", notification_channel_enum, nullable=False, server_default="in_app"),
        sa.Column("status", notification_status_enum, nullable=False, server_default="pending"),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_status", "notifications", ["status"])

    op.create_table(
        "bso_attachments",
        sa.Column("master_request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("uploaded_by_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("attachment_type", attachment_type_enum, nullable=False, server_default="bso"),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=128), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["master_request_id"], ["master_requests.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_bso_attachments_master_request_id", "bso_attachments", ["master_request_id"])
    op.create_index("ix_bso_attachments_uploaded_by_id", "bso_attachments", ["uploaded_by_id"])


def downgrade() -> None:
    op.drop_index("ix_bso_attachments_uploaded_by_id", table_name="bso_attachments")
    op.drop_index("ix_bso_attachments_master_request_id", table_name="bso_attachments")
    op.drop_table("bso_attachments")

    op.drop_index("ix_notifications_status", table_name="notifications")
    op.drop_index("ix_notifications_user_id", table_name="notifications")
    op.drop_table("notifications")

    op.drop_index("ix_audit_logs_created_at", table_name="audit_logs")
    op.drop_index("ix_audit_logs_entity_type", table_name="audit_logs")
    op.drop_index("ix_audit_logs_actor_user_id", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index("ix_payouts_approved_by_id", table_name="payouts")
    op.drop_index("ix_payouts_payout_rate_id", table_name="payouts")
    op.drop_index("ix_payouts_promoter_id", table_name="payouts")
    op.drop_index("ix_payouts_session_id", table_name="payouts")
    op.drop_index("ix_payouts_route_id", table_name="payouts")
    op.drop_table("payouts")

    op.drop_index("ix_photo_reports_reviewed_by_id", table_name="photo_reports")
    op.drop_index("ix_photo_reports_point_id", table_name="photo_reports")
    op.drop_index("ix_photo_reports_promoter_id", table_name="photo_reports")
    op.drop_index("ix_photo_reports_session_id", table_name="photo_reports")
    op.drop_index("ix_photo_reports_route_id", table_name="photo_reports")
    op.drop_table("photo_reports")

    op.drop_index("ix_geo_pings_captured_at", table_name="geo_pings")
    op.drop_index("ix_geo_pings_point_id", table_name="geo_pings")
    op.drop_index("ix_geo_pings_promoter_id", table_name="geo_pings")
    op.drop_index("ix_geo_pings_route_id", table_name="geo_pings")
    op.drop_index("ix_geo_pings_session_id", table_name="geo_pings")
    op.drop_table("geo_pings")

    op.drop_index("ix_expense_approvals_approver_id", table_name="expense_approvals")
    op.drop_index("ix_expense_approvals_expense_plan_id", table_name="expense_approvals")
    op.drop_table("expense_approvals")

    op.drop_index("ix_promoter_sessions_promoter_id", table_name="promoter_sessions")
    op.drop_index("ix_promoter_sessions_route_id", table_name="promoter_sessions")
    op.drop_table("promoter_sessions")

    op.drop_index("ix_route_points_route_id", table_name="route_points")
    op.drop_table("route_points")

    op.drop_index("ix_master_requests_assignee_id", table_name="master_requests")
    op.drop_index("ix_master_requests_requester_id", table_name="master_requests")
    op.drop_index("ix_master_requests_branch_id", table_name="master_requests")
    op.drop_table("master_requests")

    op.drop_index("ix_routes_work_date", table_name="routes")
    op.drop_index("ix_routes_payout_rate_id", table_name="routes")
    op.drop_index("ix_routes_created_by_id", table_name="routes")
    op.drop_index("ix_routes_promoter_id", table_name="routes")
    op.drop_index("ix_routes_branch_id", table_name="routes")
    op.drop_table("routes")

    op.drop_index("ix_expense_plans_created_by_id", table_name="expense_plans")
    op.drop_index("ix_expense_plans_branch_id", table_name="expense_plans")
    op.drop_table("expense_plans")

    op.drop_index("ix_payout_rates_created_by_id", table_name="payout_rates")
    op.drop_index("ix_payout_rates_role_id", table_name="payout_rates")
    op.drop_index("ix_payout_rates_branch_id", table_name="payout_rates")
    op.drop_table("payout_rates")

    op.drop_index("ix_users_branch_id", table_name="users")
    op.drop_index("ix_users_role_id", table_name="users")
    op.drop_table("users")

    op.drop_table("branches")
    op.drop_table("roles")

    enums = [
        attachment_type_enum,
        master_request_status_enum,
        expense_approval_decision_enum,
        expense_plan_status_enum,
        notification_status_enum,
        notification_channel_enum,
        payout_status_enum,
        payout_rate_type_enum,
        photo_report_status_enum,
        geo_ping_source_enum,
        promoter_session_status_enum,
        route_point_type_enum,
        route_status_enum,
        user_status_enum,
    ]
    bind = op.get_bind()
    for enum in enums:
        enum.drop(bind, checkfirst=True)
