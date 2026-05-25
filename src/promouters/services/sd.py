"""SD (сервисный документ) report — list of orders currently in SD-pending states.

Ported from PythonProject2/master_admin.py SD views. Aggregates orders by SD
price and outstanding zpch/debt amounts.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from promouters.models.service_ops import Order
from promouters.models.users import User


SD_STATUSES = ("to_sd", "done_pending_sum", "done")


def list_sd_orders(
    db: Session,
    *,
    master_tg_id: int | None = None,
    city_id: int | None = None,
) -> list[Order]:
    stmt = (
        select(Order)
        .options(selectinload(Order.city_rel))
        .where(Order.status.in_(SD_STATUSES))
        .order_by(Order.created_at.desc())
    )
    if master_tg_id:
        stmt = stmt.where(Order.assigned_to == master_tg_id)
    if city_id:
        stmt = stmt.where(Order.city_id == city_id)
    return list(db.scalars(stmt))


def sd_report(
    db: Session,
    *,
    master_tg_id: int | None = None,
    city_id: int | None = None,
) -> dict[str, Any]:
    orders = list_sd_orders(db, master_tg_id=master_tg_id, city_id=city_id)

    by_master: dict[int | None, dict[str, Any]] = defaultdict(
        lambda: {"name": "Не назначен", "orders": [], "sd_total": 0.0, "zpch_total": 0.0}
    )

    for order in orders:
        bucket = by_master[order.assigned_to]
        bucket["orders"].append(order)
        bucket["sd_total"] += float(order.sd_price or 0)
        bucket["zpch_total"] += float(order.zpch_sum or 0)

    master_ids = {key for key in by_master.keys() if key}
    if master_ids:
        masters = {
            m.tg_id: m for m in db.scalars(select(User).where(User.tg_id.in_(master_ids)))
        }
        for tg_id, bucket in by_master.items():
            master = masters.get(tg_id) if tg_id else None
            if master:
                bucket["name"] = (
                    master.full_name
                    or master.name
                    or f"{master.first_name} {master.last_name}".strip()
                )

    total_sd = round(sum(float(o.sd_price or 0) for o in orders), 2)
    total_zpch = round(sum(float(o.zpch_sum or 0) for o in orders), 2)
    total_debt = round(sum(float(o.debt_amount or 0) for o in orders), 2)

    return {
        "orders": orders,
        "by_master": dict(by_master),
        "totals": {
            "count": len(orders),
            "sd_total": total_sd,
            "zpch_total": total_zpch,
            "debt_total": total_debt,
        },
    }
