from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from promouters.db.base import Base
from promouters.models.common import TimestampMixin, UUIDPrimaryKeyMixin
from promouters.models.enums import UserStatus


class Role(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "roles"

    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    users: Mapped[list["User"]] = relationship(back_populates="role")
    payout_rates: Mapped[list["PayoutRate"]] = relationship(back_populates="role")


class Branch(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "branches"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    city: Mapped[str | None] = mapped_column(String(128), nullable=True)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    users: Mapped[list["User"]] = relationship(back_populates="branch")
    routes: Mapped[list["Route"]] = relationship(back_populates="branch")
    payout_rates: Mapped[list["PayoutRate"]] = relationship(back_populates="branch")
    expense_plans: Mapped[list["ExpensePlan"]] = relationship(back_populates="branch")
    master_requests: Mapped[list["MasterRequest"]] = relationship(back_populates="branch")
    audit_logs: Mapped[list["AuditLog"]] = relationship(back_populates="branch")


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32), unique=True, nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    middle_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[UserStatus] = mapped_column(
        Enum(
            UserStatus,
            name="user_status_enum",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        default=UserStatus.ACTIVE,
        nullable=False,
    )
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # PJ2-derived fields (bridge for VK bot compatibility)
    tg_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, nullable=True, index=True)
    vk_id: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True, index=True)
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    full_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    master_percentage: Mapped[float | None] = mapped_column(Float, nullable=True)
    passport_photo_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Denormalized role code kept in sync with roles.code via DB trigger (migration 0009)
    role_code_denorm: Mapped[str | None] = mapped_column("role", String(50), nullable=True)

    role_id: Mapped[str] = mapped_column(ForeignKey("roles.id", ondelete="RESTRICT"), nullable=False)
    branch_id: Mapped[str | None] = mapped_column(ForeignKey("branches.id", ondelete="SET NULL"))
    city_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("cities.id", ondelete="SET NULL"), nullable=True, index=True)

    role: Mapped["Role"] = relationship(back_populates="users")
    branch: Mapped["Branch | None"] = relationship(back_populates="users")
    city_rel: Mapped["City | None"] = relationship("City", foreign_keys=[city_id], lazy="select")
    assigned_routes: Mapped[list["Route"]] = relationship(
        back_populates="promoter",
        foreign_keys="Route.promoter_id",
    )
    created_routes: Mapped[list["Route"]] = relationship(
        back_populates="created_by",
        foreign_keys="Route.created_by_id",
    )
    sessions: Mapped[list["PromoterSession"]] = relationship(
        back_populates="promoter",
        foreign_keys="PromoterSession.promoter_id",
    )
    accepted_promoter_sessions: Mapped[list["PromoterSession"]] = relationship(
        back_populates="accepted_by_director",
        foreign_keys="PromoterSession.accepted_by_director_id",
    )
    forwarded_promoter_sessions: Mapped[list["PromoterSession"]] = relationship(
        back_populates="forwarded_by",
        foreign_keys="PromoterSession.forwarded_by_id",
    )
    photo_reports: Mapped[list["PhotoReport"]] = relationship(
        back_populates="promoter",
        foreign_keys="PhotoReport.promoter_id",
    )
    reviewed_photo_reports: Mapped[list["PhotoReport"]] = relationship(
        back_populates="reviewed_by",
        foreign_keys="PhotoReport.reviewed_by_id",
    )
    payouts: Mapped[list["Payout"]] = relationship(
        back_populates="promoter",
        foreign_keys="Payout.promoter_id",
    )
    approved_payouts: Mapped[list["Payout"]] = relationship(
        back_populates="approved_by",
        foreign_keys="Payout.approved_by_id",
    )
    payout_rates_created: Mapped[list["PayoutRate"]] = relationship(back_populates="created_by")
    audit_logs: Mapped[list["AuditLog"]] = relationship(back_populates="actor")
    notifications: Mapped[list["Notification"]] = relationship(back_populates="user")
    created_expense_plans: Mapped[list["ExpensePlan"]] = relationship(back_populates="created_by")
    expense_approvals: Mapped[list["ExpenseApproval"]] = relationship(back_populates="approver")
    requested_master_requests: Mapped[list["MasterRequest"]] = relationship(
        back_populates="requester",
        foreign_keys="MasterRequest.requester_id",
    )
    assigned_master_requests: Mapped[list["MasterRequest"]] = relationship(
        back_populates="assignee",
        foreign_keys="MasterRequest.assignee_id",
    )
    uploaded_bso_attachments: Mapped[list["BSOAttachment"]] = relationship(
        back_populates="uploaded_by"
    )
    login_sms_codes: Mapped[list["LoginSMSCode"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    master_request_comments: Mapped[list["MasterRequestComment"]] = relationship(
        back_populates="author"
    )
    master_request_status_logs: Mapped[list["MasterRequestStatusLog"]] = relationship(
        back_populates="changed_by"
    )
    master_geo_pings: Mapped[list["MasterGeoPing"]] = relationship(
        back_populates="master"
    )
    payment_details_rel: Mapped["PromoterPaymentDetails | None"] = relationship(
        "PromoterPaymentDetails",
        foreign_keys="PromoterPaymentDetails.user_id",
        uselist=False,
    )
