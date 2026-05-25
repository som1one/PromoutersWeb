"""Order CRUD ported from PythonProject2/admin_fastapi.py / dispatcher_admin.py."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session, selectinload

from promouters.models.service_ops import Order
from promouters.models.users import User


def generate_order_number(db: Session) -> int:
    """Return the next sequential order_number. PJ2 uses max+1 with a floor of 1."""
    max_num = db.scalar(select(func.max(Order.order_number)))
    return int(max_num or 0) + 1


def list_orders(
    db: Session,
    *,
    status: str | None = None,
    city_id: int | None = None,
    assigned_to: int | None = None,
    search: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> list[Order]:
    stmt = (
        select(Order)
        .options(selectinload(Order.city_rel))
        .order_by(desc(Order.created_at))
    )
    if status:
        stmt = stmt.where(Order.status == status)
    if city_id:
        stmt = stmt.where(Order.city_id == city_id)
    if assigned_to:
        stmt = stmt.where(Order.assigned_to == assigned_to)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(
            or_(
                Order.client_name.ilike(like),
                Order.client_phone.ilike(like),
                Order.street.ilike(like),
                Order.short_desc.ilike(like),
            )
        )
    stmt = stmt.limit(limit).offset(offset)
    return list(db.scalars(stmt))


def get_order(db: Session, order_id: int) -> Order | None:
    return db.scalar(
        select(Order)
        .options(selectinload(Order.city_rel))
        .where(Order.id == order_id)
    )


def get_order_by_number(db: Session, order_number: int) -> Order | None:
    return db.scalar(
        select(Order)
        .options(selectinload(Order.city_rel))
        .where(Order.order_number == order_number)
    )


def create_order(db: Session, *, payload: dict[str, Any], created_by_tg_id: int | None) -> Order:
    order = Order(
        order_number=generate_order_number(db),
        city_id=payload.get("city_id"),
        street=payload.get("street"),
        house=payload.get("house"),
        flat=payload.get("flat"),
        time_from=payload.get("time_from"),
        time_to=payload.get("time_to"),
        order_date=payload.get("order_date"),
        equip_type=payload.get("equip_type"),
        short_desc=payload.get("short_desc"),
        source=payload.get("source"),
        status=payload.get("status") or "new",
        created_by=created_by_tg_id,
        assigned_to=payload.get("assigned_to"),
        client_phone=payload.get("client_phone"),
        client_name=payload.get("client_name"),
        comment=payload.get("comment"),
        sum_amount=payload.get("sum_amount"),
        sd_price=payload.get("sd_price"),
        zpch_sum=payload.get("zpch_sum"),
        is_warranty=bool(payload.get("is_warranty", False)),
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


def update_order(db: Session, order: Order, payload: dict[str, Any]) -> Order:
    allowed = {
        "city_id", "street", "house", "flat", "time_from", "time_to",
        "order_date", "equip_type", "short_desc", "source", "status",
        "assigned_to", "client_phone", "client_name", "comment",
        "sum_amount", "paid_amount", "debt_amount", "debt_payment_date",
        "sd_price", "zpch_sum", "is_warranty", "warranty_until",
        "warranty_days", "warranty_source_order_id",
        "receipt_file_id", "receipt_file_path", "bso_file_path",
    }
    for key, value in payload.items():
        if key in allowed:
            setattr(order, key, value)
    db.commit()
    db.refresh(order)
    return order


def delete_order(db: Session, order: Order) -> None:
    db.delete(order)
    db.commit()


def list_masters_for_assignment(db: Session) -> list[User]:
    """Active users with role.code == 'master' (or PJ2 master flag) who have a tg_id."""
    from promouters.models.users import Role
    stmt = (
        select(User)
        .join(Role)
        .where(Role.code == "master", User.tg_id.is_not(None))
        .order_by(User.first_name.asc(), User.last_name.asc())
    )
    return list(db.scalars(stmt))


def status_counts(db: Session) -> dict[str, int]:
    rows = db.execute(
        select(Order.status, func.count(Order.id)).group_by(Order.status)
    ).all()
    return {status or "unknown": int(count) for status, count in rows}
