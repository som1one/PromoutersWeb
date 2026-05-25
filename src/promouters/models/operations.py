from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from promouters.db.base import Base
from promouters.models.common import TimestampMixin, UUIDPrimaryKeyMixin
from promouters.models.enums import (
    AttachmentType,
    MasterRequestStatus,
    NotificationChannel,
    NotificationStatus,
)


class AuditLog(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "audit_logs"

    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    branch_id: Mapped[str | None] = mapped_column(ForeignKey("branches.id", ondelete="SET NULL"))
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    actor: Mapped["User | None"] = relationship(back_populates="audit_logs")
    branch: Mapped["Branch | None"] = relationship(back_populates="audit_logs")


class Notification(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "notifications"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    channel: Mapped[NotificationChannel] = mapped_column(
        Enum(
            NotificationChannel,
            name="notification_channel_enum",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        default=NotificationChannel.IN_APP,
        nullable=False,
    )
    status: Mapped[NotificationStatus] = mapped_column(
        Enum(
            NotificationStatus,
            name="notification_status_enum",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        default=NotificationStatus.PENDING,
        nullable=False,
    )
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="notifications")


class MasterRequest(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "master_requests"

    branch_id: Mapped[str] = mapped_column(ForeignKey("branches.id", ondelete="CASCADE"), nullable=False)
    requester_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    assignee_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    client_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    client_phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    estimated_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    final_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="RUB", nullable=False)
    status: Mapped[MasterRequestStatus] = mapped_column(
        Enum(
            MasterRequestStatus,
            name="master_request_status_enum",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        default=MasterRequestStatus.NEW,
        nullable=False,
    )
    geo_tracking_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    handed_over_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_known_latitude: Mapped[float | None] = mapped_column(Numeric(10, 7), nullable=True)
    last_known_longitude: Mapped[float | None] = mapped_column(Numeric(10, 7), nullable=True)
    last_known_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    branch: Mapped["Branch"] = relationship(back_populates="master_requests")
    requester: Mapped["User"] = relationship(
        back_populates="requested_master_requests",
        foreign_keys=[requester_id],
    )
    assignee: Mapped["User | None"] = relationship(
        back_populates="assigned_master_requests",
        foreign_keys=[assignee_id],
    )
    attachments: Mapped[list["BSOAttachment"]] = relationship(
        back_populates="master_request",
        cascade="all, delete-orphan",
    )
    comments: Mapped[list["MasterRequestComment"]] = relationship(
        back_populates="master_request",
        cascade="all, delete-orphan",
        order_by="MasterRequestComment.created_at",
    )
    status_logs: Mapped[list["MasterRequestStatusLog"]] = relationship(
        back_populates="master_request",
        cascade="all, delete-orphan",
        order_by="MasterRequestStatusLog.created_at",
    )
    geo_pings: Mapped[list["MasterGeoPing"]] = relationship(
        back_populates="master_request",
        cascade="all, delete-orphan",
        order_by="MasterGeoPing.captured_at",
    )


class MasterRequestComment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "master_request_comments"

    master_request_id: Mapped[str] = mapped_column(
        ForeignKey("master_requests.id", ondelete="CASCADE"),
        nullable=False,
    )
    author_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    master_request: Mapped["MasterRequest"] = relationship(back_populates="comments")
    author: Mapped["User"] = relationship(back_populates="master_request_comments")


class MasterRequestStatusLog(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "master_request_status_logs"

    master_request_id: Mapped[str] = mapped_column(
        ForeignKey("master_requests.id", ondelete="CASCADE"),
        nullable=False,
    )
    changed_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    from_status: Mapped[MasterRequestStatus | None] = mapped_column(
        Enum(
            MasterRequestStatus,
            name="master_request_status_enum",
            create_type=False,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=True,
    )
    to_status: Mapped[MasterRequestStatus] = mapped_column(
        Enum(
            MasterRequestStatus,
            name="master_request_status_enum",
            create_type=False,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    master_request: Mapped["MasterRequest"] = relationship(back_populates="status_logs")
    changed_by: Mapped["User | None"] = relationship(back_populates="master_request_status_logs")


class MasterGeoPing(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "master_geo_pings"

    master_request_id: Mapped[str] = mapped_column(
        ForeignKey("master_requests.id", ondelete="CASCADE"),
        nullable=False,
    )
    master_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    latitude: Mapped[float] = mapped_column(Numeric(10, 7), nullable=False)
    longitude: Mapped[float] = mapped_column(Numeric(10, 7), nullable=False)
    accuracy_meters: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    status_at_capture: Mapped[MasterRequestStatus] = mapped_column(
        Enum(
            MasterRequestStatus,
            name="master_request_status_enum",
            create_type=False,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
    )

    master_request: Mapped["MasterRequest"] = relationship(back_populates="geo_pings")
    master: Mapped["User"] = relationship(back_populates="master_geo_pings")


class BSOAttachment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "bso_attachments"

    master_request_id: Mapped[str] = mapped_column(
        ForeignKey("master_requests.id", ondelete="CASCADE"),
        nullable=False,
    )
    uploaded_by_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    attachment_type: Mapped[AttachmentType] = mapped_column(
        Enum(
            AttachmentType,
            name="attachment_type_enum",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        default=AttachmentType.BSO,
        nullable=False,
    )
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    master_request: Mapped["MasterRequest"] = relationship(back_populates="attachments")
    uploaded_by: Mapped["User"] = relationship(back_populates="uploaded_bso_attachments")
