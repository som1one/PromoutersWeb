"""Dashboard statistics — port of PythonProject2/services/dashboard_stats.py.

Only the ``calculate_dashboard_stats`` aggregation is ported; the verbose
breakdown helpers (``calculate_detailed_stats``, ``calculate_category_table_stats``)
can be added later if the web UI needs them.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from promouters.models.service_ops import Order, Stat
from promouters.models.users import User
from promouters.services.commission import get_master_pct
from promouters.utils.order_helpers import (
    get_equip_type_name,
    get_equipment_category,
    get_status_name_ru,
)


COMPLETED_STATUS = "completed"
CANCELLED_STATUS = "cancelled"
REFUSED_STATUSES = {"declined"}
ACTIVE_STATUSES = {
    "new",
    "assigned",
    "accepted",
    "on_place",
    "to_sd",
    "done_pending_sum",
    "done",
    "scheduled",
}


PERIOD_PRESETS = ("today", "week", "month", "quarter", "year", "last_30")


def get_period_bounds(preset: str = "month") -> tuple[datetime, datetime]:
    now = datetime.now()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = now.replace(hour=23, minute=59, second=59, microsecond=999999)

    if preset == "today":
        return start, end
    if preset == "week":
        return start - timedelta(days=6), end
    if preset == "last_30":
        return start - timedelta(days=29), end
    if preset == "quarter":
        month = (now.month - 1) - (now.month - 1) % 3 + 1
        return start.replace(month=month, day=1), end
    if preset == "year":
        return start.replace(month=1, day=1), end
    # default = month
    return start.replace(day=1), end


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


def calculate_dashboard_stats(
    db: Session,
    *,
    date_from: datetime,
    date_to: datetime,
    city_id: int | None = None,
    city_name: str | None = None,
    master_id: int | None = None,
    equip_category: str | None = None,
    include_warranty: bool = True,
) -> dict[str, Any]:
    """Aggregate orders within (date_from, date_to) into dashboard cards + breakdowns."""

    stat_stmt = select(Stat).where(
        Stat.recorded_at >= date_from,
        Stat.recorded_at <= date_to,
    )
    if city_id:
        stat_stmt = stat_stmt.join(Order, Order.id == Stat.order_id).where(Order.city_id == city_id)
    if master_id:
        stat_stmt = stat_stmt.where(Stat.master_tg == master_id)

    stats = list(db.scalars(stat_stmt))
    completed_order_ids = {s.order_id for s in stats if s.order_id is not None}

    created_stmt = (
        select(Order)
        .options(selectinload(Order.city_rel))
        .where(Order.created_at >= date_from, Order.created_at <= date_to)
    )
    if city_id:
        created_stmt = created_stmt.where(Order.city_id == city_id)
    if master_id:
        created_stmt = created_stmt.where(Order.assigned_to == master_id)
    orders_created = list(db.scalars(created_stmt))

    orders_completed: list[Order] = []
    if completed_order_ids:
        completed_stmt = (
            select(Order)
            .options(selectinload(Order.city_rel))
            .where(Order.id.in_(completed_order_ids), Order.status == COMPLETED_STATUS)
        )
        if city_id:
            completed_stmt = completed_stmt.where(Order.city_id == city_id)
        if master_id:
            completed_stmt = completed_stmt.where(Order.assigned_to == master_id)
        orders_completed = list(db.scalars(completed_stmt))

    orders_dict = {o.id: o for o in orders_created}
    for o in orders_completed:
        orders_dict[o.id] = o
    orders = list(orders_dict.values())

    if equip_category:
        orders = [o for o in orders if get_equipment_category(o.equip_type) == equip_category]
    if not include_warranty:
        orders = [o for o in orders if not getattr(o, "is_warranty", False)]

    orders = [o for o in orders if (o.status or "") != CANCELLED_STATUS]

    master_ids = {o.assigned_to for o in orders if o.assigned_to}
    masters_map: dict[int, User] = {}
    if master_ids:
        masters_map = {
            m.tg_id: m for m in db.scalars(select(User).where(User.tg_id.in_(master_ids)))
        }

    if city_name is None:
        from promouters.services.cities import get_city
        if city_id:
            city = get_city(db, city_id)
            city_name = city.name if city else f"Город #{city_id}"
        else:
            city_name = "Все города"

    completed_orders = [o for o in orders if o.status == COMPLETED_STATUS]
    active_orders = [o for o in orders if o.status in ACTIVE_STATUSES]
    refused_orders = [o for o in orders if o.status in REFUSED_STATUSES]
    cash_pending_orders = [o for o in orders if o.status == "done_pending_sum"]

    gross_sum = sum(float(o.sum_amount or 0) for o in completed_orders)
    net_sum = 0.0
    master_share_total = 0.0

    masters_stats: dict[int, dict[str, Any]] = defaultdict(
        lambda: {"count": 0, "total": 0.0, "gross": 0.0, "refused": 0, "active": 0}
    )
    masters_conversions: dict[int, dict[str, int]] = defaultdict(
        lambda: {"total": 0, "closed": 0, "refused": 0}
    )
    equipment_stats: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"count": 0, "net": 0.0, "refused": 0}
    )
    source_counter: Counter[str] = Counter()
    status_counter: Counter[str] = Counter()
    city_breakdown: dict[int, dict[str, Any]] = defaultdict(
        lambda: {"name": "Без города", "count": 0, "net": 0.0}
    )
    daily_breakdown: dict[Any, dict[str, Any]] = defaultdict(
        lambda: {"completed": 0, "net": 0.0}
    )

    for order in orders:
        status_counter[order.status or "unknown"] += 1
        source = (order.source or "Не указан").strip()
        source_counter[source] += 1

        city_label = order.city_rel.name if order.city_rel else "Без города"
        city_breakdown[order.city_id or 0]["name"] = city_label
        city_breakdown[order.city_id or 0]["count"] += 1

        master_key = order.assigned_to
        if master_key:
            masters_conversions[master_key]["total"] += 1
            if order.status == COMPLETED_STATUS:
                masters_conversions[master_key]["closed"] += 1
            if order.status in REFUSED_STATUSES:
                masters_conversions[master_key]["refused"] += 1
            if order.status in ACTIVE_STATUSES:
                masters_stats[master_key]["active"] += 1

        if order.status == COMPLETED_STATUS:
            net = _safe_net_amount(order)
            net_sum += net
            pct = _resolve_master_pct(db, order, net, masters_map)
            company_part = _company_share(net, pct)
            master_share_total += net - company_part

            city_breakdown[order.city_id or 0]["net"] += net

            equip_code = order.equip_type or "other"
            equipment_stats[equip_code]["count"] += 1
            equipment_stats[equip_code]["net"] += net

            if master_key:
                masters_stats[master_key]["count"] += 1
                masters_stats[master_key]["total"] += net
                masters_stats[master_key]["gross"] += float(order.sum_amount or 0)

            created_at = order.created_at or datetime.now()
            daily_breakdown[created_at.date()]["completed"] += 1
            daily_breakdown[created_at.date()]["net"] += net
        elif order.status in REFUSED_STATUSES:
            equip_code = order.equip_type or "other"
            equipment_stats[equip_code]["refused"] += 1
            if master_key:
                masters_stats[master_key]["refused"] += 1

    cash_company_total = 0.0
    for order in cash_pending_orders:
        net = _safe_net_amount(order)
        pct = _resolve_master_pct(db, order, net, masters_map)
        cash_company_total += _company_share(net, pct)
    cash_company_total = round(cash_company_total, 2)

    period_days = max((date_to - date_from).days + 1, 1)
    conversion = round(
        (len(completed_orders) / len(orders) * 100) if orders else 0.0, 2
    )

    cards = {
        "completed": len(completed_orders),
        "total": len(orders),
        "in_progress": len(active_orders),
        "refused": len(refused_orders),
        "gross_sum": round(gross_sum, 2),
        "net_sum": round(net_sum, 2),
        "company_share": round(net_sum - master_share_total, 2),
        "avg_check": round(net_sum / len(completed_orders), 2) if completed_orders else 0.0,
        "conversion": conversion,
        "per_day": round(len(completed_orders) / period_days, 2),
        "cash_pending_sum": cash_company_total,
        "cash_pending_count": len(cash_pending_orders),
    }

    status_breakdown = [
        {"code": code, "name": get_status_name_ru(code), "count": status_counter.get(code, 0)}
        for code in (
            "new", "assigned", "accepted", "on_place", "to_sd",
            "done_pending_sum", "cancelled", "completed", "declined",
        )
    ]

    sources = [{"name": name, "count": count} for name, count in source_counter.most_common()]

    equipment = [
        {
            "code": code,
            "name": get_equip_type_name(code),
            "count": data["count"],
            "net_sum": round(data["net"], 2),
            "refused": data["refused"],
            "avg_check": round(data["net"] / data["count"], 2) if data["count"] else 0.0,
        }
        for code, data in sorted(
            equipment_stats.items(), key=lambda item: item[1]["net"], reverse=True
        )
    ]

    masters_list = []
    for master_tg, data in masters_stats.items():
        master_obj = masters_map.get(master_tg)
        if master_obj:
            name = (
                master_obj.full_name
                or master_obj.name
                or f"{master_obj.first_name or ''} {master_obj.last_name or ''}".strip()
                or f"ID {master_tg}"
            )
        else:
            name = str(master_tg) if master_tg else "Не назначен"
        totals = masters_conversions.get(master_tg, {"total": 0, "closed": 0, "refused": 0})
        conv_rate = round(totals["closed"] / totals["total"] * 100, 2) if totals["total"] else 0.0
        masters_list.append(
            {
                "id": master_tg,
                "name": name,
                "count": data["count"],
                "net_sum": round(data["total"], 2),
                "avg_check": round(data["total"] / data["count"], 2) if data["count"] else 0.0,
                "conversion": conv_rate,
                "refused": totals["refused"],
                "active": data["active"],
            }
        )
    masters_list.sort(key=lambda item: item["net_sum"], reverse=True)

    cities = [
        {
            "id": key,
            "name": info["name"],
            "count": info["count"],
            "net_sum": round(info["net"], 2),
        }
        for key, info in sorted(city_breakdown.items(), key=lambda x: x[1]["count"], reverse=True)
    ]

    daily_series = [
        {"date": day.strftime("%d.%m"), "count": data["completed"], "net_sum": round(data["net"], 2)}
        for day, data in sorted(daily_breakdown.items())
    ]

    return {
        "meta": {
            "date_from": date_from,
            "date_to": date_to,
            "period_days": period_days,
            "city_id": city_id,
            "city_name": city_name,
            "master_id": master_id,
        },
        "cards": cards,
        "status_breakdown": status_breakdown,
        "sources": sources,
        "equipment": equipment,
        "masters": masters_list,
        "cities": cities,
        "daily": daily_series,
        "cash_pending": {"count": cards["cash_pending_count"], "company_sum": cards["cash_pending_sum"]},
    }
