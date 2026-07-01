from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from promouters.db.base import Base
from promouters.models.common import TimestampMixin, UUIDPrimaryKeyMixin
from promouters.models.enums import ExpenseApprovalDecision, ExpensePlanStatus, PayoutRateType, PayoutStatus


class PayoutRate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "payout_rates"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    rate_type: Mapped[PayoutRateType] = mapped_column(
        Enum(
            PayoutRateType,
            name="payout_rate_type_enum",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="RUB", nullable=False)
    per_unit_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    active_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    active_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    branch_id: Mapped[str | None] = mapped_column(ForeignKey("branches.id", ondelete="CASCADE"))
    role_id: Mapped[str | None] = mapped_column(ForeignKey("roles.id", ondelete="SET NULL"))
    created_by_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)

    branch: Mapped["Branch | None"] = relationship(back_populates="payout_rates")
    role: Mapped["Role | None"] = relationship(back_populates="payout_rates")
    created_by: Mapped["User"] = relationship(back_populates="payout_rates_created")
    routes: Mapped[list["Route"]] = relationship(back_populates="payout_rate")
    payouts: Mapped[list["Payout"]] = relationship(back_populates="payout_rate")


class Payout(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "payouts"

    route_id: Mapped[str | None] = mapped_column(ForeignKey("routes.id", ondelete="CASCADE"), nullable=True)
    session_id: Mapped[str | None] = mapped_column(
        ForeignKey("promoter_sessions.id", ondelete="SET NULL"),
        nullable=True,
    )
    promoter_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    payout_rate_id: Mapped[str | None] = mapped_column(
        ForeignKey("payout_rates.id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="RUB", nullable=False)
    units: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    calculation_details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[PayoutStatus] = mapped_column(
        Enum(PayoutStatus, name="payout_status_enum", values_callable=lambda enum_cls: [item.value for item in enum_cls]),
        default=PayoutStatus.DRAFT,
        nullable=False,
    )
    calculated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    route: Mapped["Route"] = relationship(back_populates="payouts")
    session: Mapped["PromoterSession | None"] = relationship(back_populates="payouts")
    promoter: Mapped["User"] = relationship(back_populates="payouts", foreign_keys=[promoter_id])
    payout_rate: Mapped["PayoutRate | None"] = relationship(back_populates="payouts")
    approved_by: Mapped["User | None"] = relationship(
        back_populates="approved_payouts",
        foreign_keys=[approved_by_id],
    )


class ExpensePlan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "expense_plans"

    branch_id: Mapped[str] = mapped_column(ForeignKey("branches.id", ondelete="CASCADE"), nullable=False)
    created_by_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), default="План расходов", nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="RUB", nullable=False)
    status: Mapped[ExpensePlanStatus] = mapped_column(
        Enum(
            ExpensePlanStatus,
            name="expense_plan_status_enum",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        default=ExpensePlanStatus.DRAFT,
        nullable=False,
    )
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    branch: Mapped["Branch"] = relationship(back_populates="expense_plans")
    created_by: Mapped["User"] = relationship(back_populates="created_expense_plans")
    items: Mapped[list["ExpensePlanItem"]] = relationship(
        back_populates="expense_plan",
        cascade="all, delete-orphan",
        order_by="ExpensePlanItem.sequence",
    )
    approvals: Mapped[list["ExpenseApproval"]] = relationship(
        back_populates="expense_plan",
        cascade="all, delete-orphan",
    )


class ExpensePlanItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "expense_plan_items"

    expense_plan_id: Mapped[str] = mapped_column(
        ForeignKey("expense_plans.id", ondelete="CASCADE"),
        nullable=False,
    )
    sequence: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("1"), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    expense_plan: Mapped["ExpensePlan"] = relationship(back_populates="items")


class ExpenseApproval(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "expense_approvals"

    expense_plan_id: Mapped[str] = mapped_column(
        ForeignKey("expense_plans.id", ondelete="CASCADE"),
        nullable=False,
    )
    approver_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    decision: Mapped[ExpenseApprovalDecision] = mapped_column(
        Enum(
            ExpenseApprovalDecision,
            name="expense_approval_decision_enum",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        default=ExpenseApprovalDecision.PENDING,
        nullable=False,
    )
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    expense_plan: Mapped["ExpensePlan"] = relationship(back_populates="approvals")
    approver: Mapped["User"] = relationship(back_populates="expense_approvals")
