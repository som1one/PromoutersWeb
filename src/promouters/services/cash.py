"""Cash income aggregation and acceptance workflow ported from PythonProject2."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from promouters.models.service_ops import Order, Stat
from promouters.models.users import User
from promouters.services.financials import (
    calculate_net_amount,
    calculate_shares,
    resolve_master_pct,
)


COMPLETED_STATUS = "completed"
PENDING_CASH_STATUS = "done_pending_sum"


def _safe_net_amount(order: Order) -> float:
    return calculate_net_amount(order.sum_amount, order.zpch_sum)


def _resolve_master_pct(
    db: Session, order: Order, net_amount: float, masters_map: dict[int, User]
) -> float:
    master = masters_map.get(order.assigned_to) if order.assigned_to else None
    return resolve_master_pct(
        db,
        master=master,
        equip_type=order.equip_type,
        net_amount=net_amount,
        is_warranty=getattr(order, "is_warranty", False),
    )


def _company_share(net_amount: float, pct: float) -> float:
    company, _ = calculate_shares(net_amount, pct)
    return company


def _masters_map(db: Session, orders: list[Order]) -> dict[int, User]:
    master_ids = {order.assigned_to for order in orders if order.assigned_to}
    if not master_ids:
        return {}
    return {
        master.tg_id: master
        for master in db.scalars(select(User).where(User.tg_id.in_(master_ids)))
    }


def _ensure_stat_for_completed_order(
    db: Session,
    order: Order,
    *,
    masters_map: dict[int, User],
) -> None:
    existing = db.scalar(select(Stat).where(Stat.order_id == order.id))
    if existing is not None:
        return
    net_amount = _safe_net_amount(order)
    pct = _resolve_master_pct(db, order, net_amount, masters_map)
    company_share = _company_share(net_amount, pct)
    _ = company_share  # keeps parity with legacy calculation flow
    db.add(
        Stat(
            order_id=order.id,
            equip_type=order.equip_type,
            sum=net_amount,
            refused=False,
            master_tg=order.assigned_to,
        )
    )


def calculate_cash_income(
    db: Session,
    *,
    date_from: datetime,
    date_to: datetime,
    city_id: int | None = None,
) -> dict[str, Any]:
    stat_stmt = select(Stat).where(
        Stat.recorded_at >= date_from,
        Stat.recorded_at <= date_to,
    )
    if city_id:
        stat_stmt = stat_stmt.join(Order, Order.id == Stat.order_id).where(Order.city_id == city_id)

    stats = list(db.scalars(stat_stmt))
    order_ids = {stat.order_id for stat in stats if stat.order_id is not None}

    if not order_ids:
        return {
            "total_cash": 0.0,
            "company_share": 0.0,
            "masters_share": 0.0,
            "orders_count": 0,
            "by_city": [],
            "by_date": [],
        }

    orders_stmt = (
        select(Order)
        .options(selectinload(Order.city_rel))
        .where(Order.id.in_(order_ids), Order.status == COMPLETED_STATUS)
    )
    if city_id:
        orders_stmt = orders_stmt.where(Order.city_id == city_id)
    orders = list(db.scalars(orders_stmt))

    masters_map = _masters_map(db, orders)
    stats_by_order_id = {stat.order_id: stat for stat in stats}

    city_income: dict[int, dict[str, Any]] = defaultdict(
        lambda: {"name": "", "income": 0.0, "orders_count": 0, "total_net": 0.0}
    )
    daily_income: dict[Any, dict[str, Any]] = defaultdict(
        lambda: {"date": None, "income": 0.0, "orders_count": 0}
    )
    total_income = 0.0
    total_net = 0.0

    for order in orders:
        net = _safe_net_amount(order)
        pct = _resolve_master_pct(db, order, net, masters_map)
        share = _company_share(net, pct)
        total_income += share
        total_net += net

        city_key = order.city_id or 0
        city = city_income[city_key]
        if not city["name"]:
            city["name"] = order.city_rel.name if order.city_rel else "Без города"
        city["income"] += share
        city["orders_count"] += 1
        city["total_net"] += net

        stat = stats_by_order_id.get(order.id)
        if stat and stat.recorded_at:
            recorded = stat.recorded_at
            if recorded.tzinfo is not None:
                recorded = recorded.replace(tzinfo=None)
            key_date = recorded.date()
            daily = daily_income[key_date]
            daily["date"] = key_date
            daily["income"] += share
            daily["orders_count"] += 1

    city_list = []
    for city_key in sorted(city_income.keys()):
        city = city_income[city_key]
        city["avg_check"] = (
            round(city["total_net"] / city["orders_count"], 2)
            if city["orders_count"]
            else 0.0
        )
        city["income"] = round(city["income"], 2)
        city["total_net"] = round(city["total_net"], 2)
        city_list.append(city)

    daily_list = [daily_income[item] for item in sorted(daily_income.keys())]
    for daily in daily_list:
        daily["income"] = round(daily["income"], 2)

    return {
        "total_cash": round(total_net, 2),
        "company_share": round(total_income, 2),
        "masters_share": round(max(total_net - total_income, 0.0), 2),
        "orders_count": len(orders),
        "by_city": city_list,
        "by_date": daily_list,
    }


def list_pending_cash_orders(db: Session, *, city_id: int | None = None) -> list[Order]:
    stmt = (
        select(Order)
        .options(selectinload(Order.city_rel))
        .where(Order.status == PENDING_CASH_STATUS)
        .order_by(Order.created_at.desc())
    )
    if city_id:
        stmt = stmt.where(Order.city_id == city_id)
    return list(db.scalars(stmt))


def accept_order_cash(db: Session, order: Order) -> Order:
    masters_map = _masters_map(db, [order])
    order.status = COMPLETED_STATUS
    _ensure_stat_for_completed_order(db, order, masters_map=masters_map)
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


def accept_cash_for_master(
    db: Session,
    *,
    master_tg_id: int,
    city_id: int | None = None,
) -> list[Order]:
    stmt = select(Order).where(
        Order.assigned_to == master_tg_id,
        Order.status == PENDING_CASH_STATUS,
    )
    if city_id:
        stmt = stmt.where(Order.city_id == city_id)
    orders = list(db.scalars(stmt))
    masters_map = _masters_map(db, orders)
    for order in orders:
        order.status = COMPLETED_STATUS
        _ensure_stat_for_completed_order(db, order, masters_map=masters_map)
        db.add(order)
    db.commit()
    for order in orders:
        db.refresh(order)
    return orders
