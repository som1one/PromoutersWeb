"""Cash income report and acceptance workflow (owner / director)."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from promouters.db.session import get_db
from promouters.models.users import User
from promouters.services import cash as cash_svc
from promouters.services import cities as cities_svc
from promouters.services.financials import calculate_net_amount, calculate_shares, resolve_master_pct
from promouters.web.deps import render, require_roles


router = APIRouter()


def _safe_int(value: str | int | None) -> int | None:
    if value is None or isinstance(value, int):
        return value
    s = str(value).strip()
    if not s:
        return None
    try:
        return int(s)
    except ValueError:
        return None


def _actor_city_id(user: User) -> int | None:
    return None


@router.get("/")
async def cash_report(
    request: Request,
    city_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("owner", "director")),
):
    resolved_city_id = _safe_int(city_id)
    now = datetime.now()
    df = datetime.fromisoformat(date_from) if date_from else now.replace(day=1, hour=0, minute=0, second=0)
    dt = datetime.fromisoformat(date_to) if date_to else now.replace(hour=23, minute=59, second=59)
    report = cash_svc.calculate_cash_income(db, date_from=df, date_to=dt, city_id=resolved_city_id)

    pending_orders = cash_svc.list_pending_cash_orders(db, city_id=resolved_city_id)
    master_ids = {order.assigned_to for order in pending_orders if order.assigned_to}
    masters_map: dict[int, User] = {}
    if master_ids:
        masters_map = {
            master.tg_id: master
            for master in db.scalars(select(User).where(User.tg_id.in_(master_ids)))
        }

    grouped_masters: dict[int, dict] = {}
    for order in pending_orders:
        if not order.assigned_to:
            continue
        group = grouped_masters.setdefault(
            order.assigned_to,
            {
                "master_id": order.assigned_to,
                "master_name": "Не назначен",
                "count": 0,
                "total_sum": 0.0,
            },
        )
        master = masters_map.get(order.assigned_to)
        if master:
            group["master_name"] = (
                master.full_name
                or master.name
                or f"{master.first_name} {master.last_name}".strip()
            )
        group["count"] += 1
        # Show company share (what company actually receives) instead of raw sum_amount
        net = calculate_net_amount(order.sum_amount, order.zpch_sum)
        pct = resolve_master_pct(
            db,
            master=master,
            equip_type=order.equip_type,
            net_amount=net,
            is_warranty=getattr(order, "is_warranty", False),
        )
        company_share, _ = calculate_shares(net, pct)
        group["total_sum"] += company_share

    # Pre-compute company shares for individual orders table
    order_company_shares: dict[int, float] = {}
    for order in pending_orders:
        net = calculate_net_amount(order.sum_amount, order.zpch_sum)
        master = masters_map.get(order.assigned_to) if order.assigned_to else None
        pct = resolve_master_pct(
            db,
            master=master,
            equip_type=order.equip_type,
            net_amount=net,
            is_warranty=getattr(order, "is_warranty", False),
        )
        company, _ = calculate_shares(net, pct)
        order_company_shares[order.id] = company

    flash_success = None
    if request.query_params.get("accepted") == "order":
        flash_success = "Заявка принята в кассу."
    elif request.query_params.get("accepted") == "master":
        flash_success = "Касса мастера принята."

    return render(
        request,
        "cash.html",
        user=user,
        active_page="cash",
        report=report,
        pending_orders=pending_orders,
        pending_masters=sorted(grouped_masters.values(), key=lambda item: item["master_name"]),
        masters_map=masters_map,
        order_company_shares=order_company_shares,
        filter={"city_id": resolved_city_id, "date_from": df.date().isoformat(), "date_to": dt.date().isoformat()},
        available_cities=cities_svc.list_cities(db),
        flash_success=flash_success,
    )


@router.post("/accept-order/{order_id}")
async def cash_accept_order(
    order_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("owner", "director")),  # noqa: ARG001
):
    pending_orders = {order.id: order for order in cash_svc.list_pending_cash_orders(db)}
    order = pending_orders.get(order_id)
    if order is not None:
        cash_svc.accept_order_cash(db, order)
    return RedirectResponse("/admin/cash?accepted=order", status_code=302)


@router.post("/accept/{master_tg_id}")
async def cash_accept_master(
    master_tg_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("owner", "director")),  # noqa: ARG001
):
    cash_svc.accept_cash_for_master(db, master_tg_id=master_tg_id)
    return RedirectResponse("/admin/cash?accepted=master", status_code=302)
