from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from promouters.db.base import Base
from promouters.models.common import TimestampMixin, UUIDPrimaryKeyMixin
from promouters.models.enums import (
    GeoPingSource,
    PhotoReportStatus,
    PromoterReportReviewStatus,
    PromoterSessionStatus,
    RoutePointType,
    RouteStatus,
)


class Route(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "routes"

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    map_image_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    work_date: Mapped[date] = mapped_column(Date, nullable=False)
    planned_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    planned_end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[RouteStatus] = mapped_column(
        Enum(RouteStatus, name="route_status_enum", values_callable=lambda enum_cls: [item.value for item in enum_cls]),
        default=RouteStatus.DRAFT,
        nullable=False,
    )

    branch_id: Mapped[str] = mapped_column(ForeignKey("branches.id", ondelete="CASCADE"), nullable=False)
    promoter_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_by_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    payout_rate_id: Mapped[str | None] = mapped_column(
        ForeignKey("payout_rates.id", ondelete="SET NULL"),
        nullable=True,
    )

    branch: Mapped["Branch"] = relationship(back_populates="routes")
    promoter: Mapped["User | None"] = relationship(
        back_populates="assigned_routes",
        foreign_keys=[promoter_id],
    )
    created_by: Mapped["User"] = relationship(
        back_populates="created_routes",
        foreign_keys=[created_by_id],
    )
    payout_rate: Mapped["PayoutRate | None"] = relationship(back_populates="routes")
    points: Mapped[list["RoutePoint"]] = relationship(
        back_populates="route",
        cascade="all, delete-orphan",
        order_by="RoutePoint.sequence",
    )
    sessions: Mapped[list["PromoterSession"]] = relationship(
        back_populates="route",
        cascade="all, delete-orphan",
    )
    photo_reports: Mapped[list["PhotoReport"]] = relationship(back_populates="route")
    payouts: Mapped[list["Payout"]] = relationship(back_populates="route")


class RoutePoint(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "route_points"
    __table_args__ = (UniqueConstraint("route_id", "sequence", name="uq_route_points_route_sequence"),)

    route_id: Mapped[str] = mapped_column(ForeignKey("routes.id", ondelete="CASCADE"), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Numeric(10, 7), nullable=True)
    longitude: Mapped[float | None] = mapped_column(Numeric(10, 7), nullable=True)
    point_type: Mapped[RoutePointType] = mapped_column(
        Enum(
            RoutePointType,
            name="route_point_type_enum",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        default=RoutePointType.CHECKPOINT,
        nullable=False,
    )
    planned_arrival_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    route: Mapped["Route"] = relationship(back_populates="points")
    geo_pings: Mapped[list["GeoPing"]] = relationship(back_populates="point")
    photo_reports: Mapped[list["PhotoReport"]] = relationship(back_populates="point")


class PromoterSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "promoter_sessions"

    route_id: Mapped[str] = mapped_column(ForeignKey("routes.id", ondelete="CASCADE"), nullable=False)
    promoter_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[PromoterSessionStatus] = mapped_column(
        Enum(
            PromoterSessionStatus,
            name="promoter_session_status_enum",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        default=PromoterSessionStatus.PLANNED,
        nullable=False,
    )
    total_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    leaflet_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_latitude: Mapped[float | None] = mapped_column(Numeric(10, 7), nullable=True)
    started_longitude: Mapped[float | None] = mapped_column(Numeric(10, 7), nullable=True)
    finished_latitude: Mapped[float | None] = mapped_column(Numeric(10, 7), nullable=True)
    finished_longitude: Mapped[float | None] = mapped_column(Numeric(10, 7), nullable=True)
    review_status: Mapped[PromoterReportReviewStatus] = mapped_column(
        Enum(
            PromoterReportReviewStatus,
            name="promoter_report_review_status_enum",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        default=PromoterReportReviewStatus.PENDING,
        nullable=False,
    )
    review_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    accepted_by_director_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    forwarded_by_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    forwarded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    route: Mapped["Route"] = relationship(back_populates="sessions")
    promoter: Mapped["User"] = relationship(back_populates="sessions", foreign_keys=[promoter_id])
    accepted_by_director: Mapped["User | None"] = relationship(
        back_populates="accepted_promoter_sessions",
        foreign_keys=[accepted_by_director_id],
    )
    forwarded_by: Mapped["User | None"] = relationship(
        back_populates="forwarded_promoter_sessions",
        foreign_keys=[forwarded_by_id],
    )
    geo_pings: Mapped[list["GeoPing"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )
    photo_reports: Mapped[list["PhotoReport"]] = relationship(back_populates="session")
    payouts: Mapped[list["Payout"]] = relationship(back_populates="session")


class GeoPing(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "geo_pings"

    session_id: Mapped[str] = mapped_column(
        ForeignKey("promoter_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    route_id: Mapped[str] = mapped_column(ForeignKey("routes.id", ondelete="CASCADE"), nullable=False)
    promoter_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    point_id: Mapped[str | None] = mapped_column(ForeignKey("route_points.id", ondelete="SET NULL"))
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    latitude: Mapped[float] = mapped_column(Numeric(10, 7), nullable=False)
    longitude: Mapped[float] = mapped_column(Numeric(10, 7), nullable=False)
    accuracy_meters: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    speed_mps: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    heading_degrees: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    source: Mapped[GeoPingSource] = mapped_column(
        Enum(
            GeoPingSource,
            name="geo_ping_source_enum",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        default=GeoPingSource.TRACKING,
        nullable=False,
    )
    raw_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    session: Mapped["PromoterSession"] = relationship(back_populates="geo_pings")
    point: Mapped["RoutePoint | None"] = relationship(back_populates="geo_pings")


class PhotoReport(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "photo_reports"

    route_id: Mapped[str] = mapped_column(ForeignKey("routes.id", ondelete="CASCADE"), nullable=False)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("promoter_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    promoter_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    point_id: Mapped[str | None] = mapped_column(ForeignKey("route_points.id", ondelete="SET NULL"))
    reviewed_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    thumbnail_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    latitude: Mapped[float | None] = mapped_column(Numeric(10, 7), nullable=True)
    longitude: Mapped[float | None] = mapped_column(Numeric(10, 7), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[PhotoReportStatus] = mapped_column(
        Enum(
            PhotoReportStatus,
            name="photo_report_status_enum",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        default=PhotoReportStatus.PENDING,
        nullable=False,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    route: Mapped["Route"] = relationship(back_populates="photo_reports")
    session: Mapped["PromoterSession"] = relationship(back_populates="photo_reports")
    promoter: Mapped["User"] = relationship(
        back_populates="photo_reports",
        foreign_keys=[promoter_id],
    )
    point: Mapped["RoutePoint | None"] = relationship(back_populates="photo_reports")
    reviewed_by: Mapped["User | None"] = relationship(
        back_populates="reviewed_photo_reports",
        foreign_keys=[reviewed_by_id],
    )
