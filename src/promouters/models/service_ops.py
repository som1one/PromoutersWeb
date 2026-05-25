"""SQLAlchemy models for entities originally defined in PythonProject2/model.py.

Column names mirror PJ2's ``model.py`` 1:1 (with BigInteger substituted for
Integer where Telegram IDs are stored) so the VK and Telegram bots continue to
operate unchanged against the merged Postgres database. New web layer code
reads/writes these tables through the models declared here; the bots keep
using their own PythonProject2/model.py classes.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from promouters.db.base import Base


class City(Base):
    """Cities / branch locations used by the legacy PJ2 service-order flow.

    Uses SERIAL integer PK to remain compatible with PythonProject2/model.py's
    ``City(id=Integer)`` declaration. Promouters' own location concept lives
    in the ``branches`` table — these are intentionally separate.
    """
    __tablename__ = "cities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    cash_company_percentage: Mapped[float | None] = mapped_column(Float, default=50.0, nullable=True)
    timezone: Mapped[str | None] = mapped_column(String(100), default="Europe/Moscow", nullable=True)


class EquipmentType(Base):
    __tablename__ = "equipment_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    master_pct: Mapped[float | None] = mapped_column(Float, default=60.0, nullable=True)
    company_pct: Mapped[float | None] = mapped_column(Float, default=40.0, nullable=True)


class Order(Base):
    """Service order — clients call in, dispatcher creates, master fulfils."""
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_number: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    city_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("cities.id"), nullable=True, index=True
    )

    # Address
    street: Mapped[str | None] = mapped_column(String(500), nullable=True)
    house: Mapped[str | None] = mapped_column(String(100), nullable=True)
    flat: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Scheduling — PJ2 stores time as free-text strings, not TIME columns.
    time_from: Mapped[str | None] = mapped_column(String(50), nullable=True)
    time_to: Mapped[str | None] = mapped_column(String(50), nullable=True)
    order_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    equip_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    short_desc: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="new", nullable=False)

    # PJ2 declares FKs to users.tg_id at the model level. We keep them at the
    # SQL level too — same as PJ2's model.py. Stored as BigInteger to fit
    # full Telegram IDs.
    created_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    assigned_to: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)

    client_phone: Mapped[str | None] = mapped_column(String(100), nullable=True)
    client_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    sum_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    paid_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    debt_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    debt_payment_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sd_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    zpch_sum: Mapped[float | None] = mapped_column(Float, nullable=True)

    is_warranty: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    warranty_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    warranty_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    warranty_source_order_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    receipt_file_id: Mapped[str | None] = mapped_column(String(500), nullable=True)
    receipt_file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    bso_file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    city_rel: Mapped["City | None"] = relationship("City", foreign_keys=[city_id])


class Stat(Base):
    __tablename__ = "stats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    equip_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    sum: Mapped[float | None] = mapped_column(Float, default=0.0, nullable=True)
    refused: Mapped[bool | None] = mapped_column(Boolean, default=False, nullable=True)
    master_tg: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Attendance(Base):
    __tablename__ = "attendance"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    master_tg_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    check_in_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    is_penalty: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Penalty(Base):
    __tablename__ = "penalties"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    master_tg_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    attendance_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("attendance.id"), nullable=True
    )
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    amount: Mapped[float | None] = mapped_column(Float, default=0.0, nullable=True)
    reason: Mapped[str | None] = mapped_column(
        String(500),
        default="Опоздание на смену (отметка не сделана до 9:00)",
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SystemSettings(Base):
    __tablename__ = "system_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    value: Mapped[str | None] = mapped_column(String(500), nullable=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
