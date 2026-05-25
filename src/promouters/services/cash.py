"""Cash income aggregation — port of PythonProject2.services.dashboard_stats.calculate_cash_income.

Calculates the company's share of completed orders within a period, grouped
by city and date.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from promouters.models.service_ops import Order, Stat
from promouters.models.users import User
from promouters.services.commission import get_master_pct


COMPLETED_STATUS = "completed"


def _safe_net_amount(order: Order) -> float:
    return round(
        max(
            float(order.sum_amount or 0)
            - float(order.sd_price or 0)
            - float(order.zpch_sum or 0),
            0.0,
        ),
        2,
    )


def _resolve_master_pct(
    db: Session, order: Order, net_amount: float, masters_map: dict[int, User]
) -> float:
    if getattr(order, "is_warranty", False):
        return 50.0
    if order.assigned_to:
        master = masters_map.get(order.assigned_to)
        if master and master.master_percentage is not None:
            return float(master.master_percentage)
    try:
        return float(get_master_pct(db, order.equip_type, net_amount))
    except Exception:
        return 40.0


def _company_share(net_amount: float, pct: float) -> float:
    return round(max(net_amount - net_amount * (pct / 100.0), 0.0), 2)


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
    order_ids = {s.order_id for s in stats if s.order_id is not None}

    if not order_ids:
        return {"total_income": 0.0, "by_city": [], "by_date": [], "total_orders": 0}

    orders_stmt = (
        select(Order)
        .options(selectinload(Order.city_rel))
        .where(Order.id.in_(order_ids), Order.status == COMPLETED_STATUS)
    )
    if city_id:
        orders_stmt = orders_stmt.where(Order.city_id == city_id)
    orders = list(db.scalars(orders_stmt))

    master_ids = {o.assigned_to for o in orders if o.assigned_to}
    masters_map: dict[int, User] = {}
    if master_ids:
        masters_map = {
            m.tg_id: m for m in db.scalars(
                select(User).where(User.tg_id.in_(master_ids))
            )
        }

    stats_by_order_id = {s.order_id: s for s in stats}

    city_income: dict[int, dict[str, Any]] = defaultdict(
        lambda: {"name": "", "income": 0.0, "orders_count": 0, "total_net": 0.0}
    )
    daily_income: dict[Any, dict[str, Any]] = defaultdict(
        lambda: {"date": None, "income": 0.0, "orders_count": 0}
    )
    total_income = 0.0

    for order in orders:
        net = _safe_net_amount(order)
        pct = _resolve_master_pct(db, order, net, masters_map)
        share = _company_share(net, pct)
        total_income += share

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

    daily_list = [daily_income[d] for d in sorted(daily_income.keys())]
    for daily in daily_list:
        daily["income"] = round(daily["income"], 2)

    return {
        "total_income": round(total_income, 2),
        "by_city": city_list,
        "by_date": daily_list,
        "total_orders": len(orders),
    }
