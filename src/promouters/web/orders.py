"""Service-order admin: list, view, create, edit, delete (ported from PJ2)."""
from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from promouters.db.session import get_db
from promouters.models.users import User
from promouters.services import cities as cities_svc
from promouters.services import orders as orders_svc
from promouters.utils.order_helpers import (
    STATUS_NAMES_RU,
    get_equip_type_name,
    get_status_name_ru,
)
from promouters.web.deps import render, require_roles


router = APIRouter()


ORDER_ROLES = ("owner", "director", "dispatcher", "branch_manager", "ad_director")


def _status_badge_class(status: str | None) -> str:
    return {
        "completed": "badge-success",
        "done": "badge-success",
        "cancelled": "badge-muted",
        "declined": "badge-danger",
        "new": "badge-info",
        "assigned": "badge-info",
        "on_place": "badge-warning",
        "to_sd": "badge-warning",
        "done_pending_sum": "badge-warning",
    }.get(status or "", "badge")


def _decorate(order, masters_map: dict[int, User] | None = None):
    address_parts = [p for p in (order.street, order.house, order.flat) if p]
    address = ", ".join(address_parts) if address_parts else "—"
    assignee = (masters_map or {}).get(order.assigned_to) if order.assigned_to else None
    assignee_name = (
        assignee.full_name
        or assignee.name
        or f"{assignee.first_name} {assignee.last_name}".strip()
    ) if assignee else None
    return SimpleNamespace(
        id=order.id,
        order_number=order.order_number,
        order_date=order.order_date,
        status=order.status,
        status_name=get_status_name_ru(order.status),
        status_badge_class=_status_badge_class(order.status),
        equip_type=order.equip_type,
        equip_type_name=get_equip_type_name(order.equip_type),
        address_short=address,
        sum_amount=order.sum_amount,
        assignee_name=assignee_name,
        assigned_to=order.assigned_to,
        client_name=order.client_name,
        client_phone=order.client_phone,
        city_rel=order.city_rel,
        short_desc=order.short_desc,
        comment=order.comment,
        sd_price=order.sd_price,
        zpch_sum=order.zpch_sum,
        time_from=order.time_from,
        time_to=order.time_to,
        is_warranty=order.is_warranty,
        receipt_file_path=order.receipt_file_path,
        bso_file_path=order.bso_file_path,
        created_at=order.created_at,
    )


@router.get("/")
async def orders_list(
    request: Request,
    status: str | None = None,
    city_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*ORDER_ROLES)),
):
    raw_orders = orders_svc.list_orders(db, status=status, city_id=city_id)
    master_ids = {o.assigned_to for o in raw_orders if o.assigned_to}
    masters_map: dict[int, User] = {}
    if master_ids:
        from sqlalchemy import select
        masters_map = {
            m.tg_id: m for m in db.scalars(select(User).where(User.tg_id.in_(master_ids)))
        }
    decorated = [_decorate(o, masters_map) for o in raw_orders]

    return render(
        request,
        "orders_list.html",
        user=user,
        active_page="orders",
        orders=decorated,
        total=len(decorated),
        filter={"status": status, "city_id": city_id, "date_from": None, "date_to": None},
        available_statuses=[{"code": c, "name": n} for c, n in STATUS_NAMES_RU.items()],
        available_cities=cities_svc.list_cities(db),
    )


@router.get("/create")
async def order_create_form(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*ORDER_ROLES)),
):
    return render(
        request,
        "create_order.html",
        user=user,
        active_page="order_create",
        cities=cities_svc.list_cities(db),
        masters=orders_svc.list_masters_for_assignment(db),
        equip_choices=[(name, code) for name, code in [("Бытовая", "appliance"), ("ПК", "pc"), ("Телевизоры", "phones"), ("Другое", "other")]],
    )


@router.post("/create")
async def order_create_submit(
    request: Request,
    city_id: int | None = Form(None),
    street: str | None = Form(None),
    house: str | None = Form(None),
    flat: str | None = Form(None),
    time_from: str | None = Form(None),
    time_to: str | None = Form(None),
    order_date: str | None = Form(None),
    equip_type: str | None = Form(None),
    short_desc: str | None = Form(None),
    source: str | None = Form(None),
    client_name: str | None = Form(None),
    client_phone: str | None = Form(None),
    assigned_to: int | None = Form(None),
    sum_amount: float | None = Form(None),
    is_warranty: bool = Form(False),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*ORDER_ROLES)),
):
    parsed_date: datetime | None = None
    if order_date:
        try:
            parsed_date = datetime.fromisoformat(order_date)
        except ValueError:
            parsed_date = None

    order = orders_svc.create_order(
        db,
        payload={
            "city_id": city_id,
            "street": street,
            "house": house,
            "flat": flat,
            "time_from": time_from,
            "time_to": time_to,
            "order_date": parsed_date,
            "equip_type": equip_type,
            "short_desc": short_desc,
            "source": source,
            "client_name": client_name,
            "client_phone": client_phone,
            "assigned_to": assigned_to,
            "sum_amount": sum_amount,
            "is_warranty": is_warranty,
        },
        created_by_tg_id=user.tg_id,
    )
    return RedirectResponse(f"/admin/orders/{order.id}?created=1", status_code=302)


@router.get("/{order_id}")
async def order_detail(
    request: Request,
    order_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*ORDER_ROLES)),
):
    order = orders_svc.get_order(db, order_id)
    if not order:
        return render(request, "404.html", user=user, status_code=404, what="Заявка")
    masters_map: dict[int, User] = {}
    if order.assigned_to:
        from sqlalchemy import select
        masters_map = {
            m.tg_id: m for m in db.scalars(select(User).where(User.tg_id == order.assigned_to))
        }
    decorated = _decorate(order, masters_map)
    return render(
        request,
        "order_view.html",
        user=user,
        active_page="orders",
        order=decorated,
        cities=cities_svc.list_cities(db),
        masters=orders_svc.list_masters_for_assignment(db),
    )


@router.post("/{order_id}/update")
async def order_update(
    request: Request,
    order_id: int,
    status: str | None = Form(None),
    assigned_to: int | None = Form(None),
    sum_amount: float | None = Form(None),
    sd_price: float | None = Form(None),
    zpch_sum: float | None = Form(None),
    comment: str | None = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*ORDER_ROLES)),
):
    order = orders_svc.get_order(db, order_id)
    if not order:
        return RedirectResponse("/admin/orders?error=notfound", status_code=302)
    payload = {
        k: v
        for k, v in {
            "status": status,
            "assigned_to": assigned_to,
            "sum_amount": sum_amount,
            "sd_price": sd_price,
            "zpch_sum": zpch_sum,
            "comment": comment,
        }.items()
        if v is not None and v != ""
    }
    orders_svc.update_order(db, order, payload)
    return RedirectResponse(f"/admin/orders/{order_id}?updated=1", status_code=302)


@router.post("/{order_id}/delete")
async def order_delete(
    order_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("owner", "director")),  # noqa: ARG001
):
    order = orders_svc.get_order(db, order_id)
    if order:
        orders_svc.delete_order(db, order)
    return RedirectResponse("/admin/orders?deleted=1", status_code=302)
