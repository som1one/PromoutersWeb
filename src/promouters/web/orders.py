"""Service-order admin: list, view, create, edit, delete (ported from PJ2)."""
from __future__ import annotations

from datetime import date, datetime
from types import SimpleNamespace

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from promouters.db.session import get_db
from promouters.models.users import User
from promouters.services import cities as cities_svc
from promouters.services import orders as orders_svc
from promouters.utils.order_helpers import (
    EQUIP_TYPES,
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
    address_parts = [part for part in (order.street, order.house, order.flat) if part]
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
        status_code=order.status,
        status_name=get_status_name_ru(order.status),
        status_badge_class=_status_badge_class(order.status),
        equip_type=order.equip_type,
        equip_type_name=get_equip_type_name(order.equip_type),
        address_short=address,
        sum_amount=order.sum_amount,
        paid_amount=order.paid_amount,
        debt_amount=order.debt_amount,
        assignee_name=assignee_name,
        assigned_to=order.assigned_to,
        client_name=order.client_name,
        client_phone=order.client_phone,
        city_rel=order.city_rel,
        city_id=order.city_id,
        street=order.street,
        house=order.house,
        flat=order.flat,
        short_desc=order.short_desc,
        comment=order.comment,
        source=order.source,
        sd_price=order.sd_price,
        zpch_sum=order.zpch_sum,
        time_from=order.time_from,
        time_to=order.time_to,
        is_warranty=order.is_warranty,
        receipt_file_path=order.receipt_file_path,
        bso_file_path=order.bso_file_path,
        created_at=order.created_at,
    )


def _parse_range(
    date_from: str | None,
    date_to: str | None,
    period: str | None,
) -> tuple[datetime | None, datetime | None]:
    if not date_from and not date_to and not period:
        today = date.today()
        date_from = today.replace(day=1).isoformat()
        date_to = today.isoformat()
    start_dt = (
        datetime.fromisoformat(date_from).replace(hour=0, minute=0, second=0, microsecond=0)
        if date_from else None
    )
    end_dt = (
        datetime.fromisoformat(date_to).replace(hour=23, minute=59, second=59, microsecond=999999)
        if date_to else None
    )
    return start_dt, end_dt


def _parse_order_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _order_payload_from_form(
    *,
    city_id: str | int | None,
    street: str | None,
    house: str | None,
    flat: str | None,
    time_from: str | None,
    time_to: str | None,
    order_date: str | None,
    equip_type: str | None,
    short_desc: str | None,
    source: str | None,
    client_name: str | None,
    client_phone: str | None,
    assigned_to: str | None,
    sum_amount: str | float | None,
    sd_price: str | float | None = None,
    zpch_sum: str | float | None = None,
    comment: str | None = None,
    status: str | None = None,
    is_warranty: bool = False,
) -> dict:
    # Parse assigned_to: empty string → None, otherwise int
    parsed_assigned_to: int | None = None
    if assigned_to and str(assigned_to).strip():
        try:
            parsed_assigned_to = int(str(assigned_to).strip())
        except ValueError:
            parsed_assigned_to = None

    # Parse numeric fields: empty string → None
    def _parse_int(val: str | int | None) -> int | None:
        if val is None:
            return None
        s = str(val).strip()
        if not s:
            return None
        try:
            return int(s)
        except ValueError:
            return None

    def _parse_float(val: str | float | None) -> float | None:
        if val is None:
            return None
        s = str(val).strip()
        if not s:
            return None
        try:
            return float(s)
        except ValueError:
            return None

    payload = {
        "city_id": _parse_int(city_id),
        "street": street,
        "house": house,
        "flat": flat,
        "time_from": time_from,
        "time_to": time_to,
        "order_date": _parse_order_date(order_date),
        "equip_type": equip_type,
        "short_desc": short_desc,
        "source": source,
        "client_name": client_name,
        "client_phone": client_phone,
        "assigned_to": parsed_assigned_to,
        "sum_amount": _parse_float(sum_amount),
        "sd_price": _parse_float(sd_price),
        "zpch_sum": _parse_float(zpch_sum),
        "comment": comment,
        "status": status,
        "is_warranty": is_warranty,
    }
    return {
        key: value
        for key, value in payload.items()
        if value is not None and value != ""
    }


@router.get("/")
async def orders_list(
    request: Request,
    status: str | None = None,
    city_id: int | None = None,
    search: str | None = None,
    master_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    period: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*ORDER_ROLES)),
):
    start_dt, end_dt = _parse_range(date_from, date_to, period)
    raw_orders = orders_svc.list_orders(
        db,
        status=status,
        city_id=city_id,
        assigned_to=master_id,
        search=search,
        date_from=start_dt,
        date_to=end_dt,
    )
    master_ids = {order.assigned_to for order in raw_orders if order.assigned_to}
    masters_map: dict[int, User] = {}
    if master_ids:
        from sqlalchemy import select

        masters_map = {
            master.tg_id: master
            for master in db.scalars(select(User).where(User.tg_id.in_(master_ids)))
        }
    decorated = [_decorate(order, masters_map) for order in raw_orders]

    role = user.role.code if user.role else None
    can_close = role in ("owner", "branch_manager", "dispatcher")

    return render(
        request,
        "orders_list.html",
        user=user,
        active_page="orders",
        orders=decorated,
        total=len(decorated),
        can_close=can_close,
        filter={
            "status": status or "",
            "city_id": city_id,
            "date_from": start_dt.date().isoformat() if start_dt else "",
            "date_to": end_dt.date().isoformat() if end_dt else "",
            "search": search or "",
            "master_id": master_id,
        },
        available_statuses=[{"code": code, "name": name} for code, name in STATUS_NAMES_RU.items()],
        available_cities=cities_svc.list_cities(db),
        masters=orders_svc.list_masters_for_assignment(db),
    )


@router.get("/search")
async def orders_search(
    request: Request,
    phone: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*ORDER_ROLES)),
):
    raw_orders = orders_svc.list_orders(db, search=phone.strip() if phone else None)
    master_ids = {order.assigned_to for order in raw_orders if order.assigned_to}
    masters_map: dict[int, User] = {}
    if master_ids:
        from sqlalchemy import select

        masters_map = {
            master.tg_id: master
            for master in db.scalars(select(User).where(User.tg_id.in_(master_ids)))
        }
    decorated = [_decorate(order, masters_map) for order in raw_orders]
    return render(
        request,
        "order_search.html",
        user=user,
        active_page="orders",
        phone=phone or "",
        orders=decorated,
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
        available_cities=cities_svc.list_cities(db),
        masters=orders_svc.list_masters_for_assignment(db),
        available_equip_types=[
            SimpleNamespace(code=code, name=name) for name, code in EQUIP_TYPES
        ],
        is_edit=False,
        order_data=None,
    )


@router.post("/create")
async def order_create_submit(
    city_id: str | None = Form(None),
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
    assigned_to: str | None = Form(None),
    sum_amount: str | None = Form(None),
    sd_price: str | None = Form(None),
    zpch_sum: str | None = Form(None),
    comment: str | None = Form(None),
    is_warranty: bool = Form(False),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*ORDER_ROLES)),
):
    order = orders_svc.create_order(
        db,
        payload=_order_payload_from_form(
            city_id=city_id,
            street=street,
            house=house,
            flat=flat,
            time_from=time_from,
            time_to=time_to,
            order_date=order_date,
            equip_type=equip_type,
            short_desc=short_desc,
            source=source,
            client_name=client_name,
            client_phone=client_phone,
            assigned_to=assigned_to,
            sum_amount=sum_amount,
            sd_price=sd_price,
            zpch_sum=zpch_sum,
            comment=comment,
            is_warranty=is_warranty,
        ),
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
            master.tg_id: master
            for master in db.scalars(select(User).where(User.tg_id == order.assigned_to))
        }
    decorated = _decorate(order, masters_map)

    flash_success = None
    if request.query_params.get("created"):
        flash_success = "Заявка создана."
    elif request.query_params.get("updated"):
        flash_success = "Заявка обновлена."

    return render(
        request,
        "order_view.html",
        user=user,
        active_page="orders",
        order=decorated,
        cities=cities_svc.list_cities(db),
        masters=orders_svc.list_masters_for_assignment(db),
        available_statuses=[{"code": code, "name": name} for code, name in STATUS_NAMES_RU.items()],
        flash_success=flash_success,
    )


@router.get("/{order_id}/edit")
async def order_edit_form(
    request: Request,
    order_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*ORDER_ROLES)),
):
    order = orders_svc.get_order(db, order_id)
    if not order:
        return render(request, "404.html", user=user, status_code=404, what="Заявка")
    return render(
        request,
        "create_order.html",
        user=user,
        active_page="orders",
        available_cities=cities_svc.list_cities(db),
        masters=orders_svc.list_masters_for_assignment(db),
        available_equip_types=[
            SimpleNamespace(code=code, name=name) for name, code in EQUIP_TYPES
        ],
        is_edit=True,
        order_data=order,
    )


@router.post("/{order_id}/update")
async def order_update(
    order_id: int,
    status: str | None = Form(None),
    assigned_to: str | None = Form(None),
    sum_amount: str | None = Form(None),
    sd_price: str | None = Form(None),
    zpch_sum: str | None = Form(None),
    comment: str | None = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*ORDER_ROLES)),  # noqa: ARG001
):
    order = orders_svc.get_order(db, order_id)
    if not order:
        return RedirectResponse("/admin/orders?error=notfound", status_code=302)

    # Parse numeric fields from form strings
    def _safe_int(val: str | None) -> int | None:
        if not val or not val.strip():
            return None
        try:
            return int(val.strip())
        except ValueError:
            return None

    def _safe_float(val: str | None) -> float | None:
        if not val or not val.strip():
            return None
        try:
            return float(val.strip())
        except ValueError:
            return None

    payload = {
        key: value
        for key, value in {
            "status": status,
            "assigned_to": _safe_int(assigned_to),
            "sum_amount": _safe_float(sum_amount),
            "sd_price": _safe_float(sd_price),
            "zpch_sum": _safe_float(zpch_sum),
            "comment": comment,
        }.items()
        if value is not None and value != ""
    }
    orders_svc.update_order(db, order, payload)
    return RedirectResponse(f"/admin/orders/{order_id}?updated=1", status_code=302)


@router.post("/{order_id}")
async def order_edit_submit(
    order_id: int,
    city_id: str | None = Form(None),
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
    assigned_to: str | None = Form(None),
    sum_amount: str | None = Form(None),
    sd_price: str | None = Form(None),
    zpch_sum: str | None = Form(None),
    comment: str | None = Form(None),
    status: str | None = Form(None),
    is_warranty: bool = Form(False),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*ORDER_ROLES)),  # noqa: ARG001
):
    order = orders_svc.get_order(db, order_id)
    if not order:
        return RedirectResponse("/admin/orders?error=notfound", status_code=302)
    orders_svc.update_order(
        db,
        order,
        _order_payload_from_form(
            city_id=city_id,
            street=street,
            house=house,
            flat=flat,
            time_from=time_from,
            time_to=time_to,
            order_date=order_date,
            equip_type=equip_type,
            short_desc=short_desc,
            source=source,
            client_name=client_name,
            client_phone=client_phone,
            assigned_to=assigned_to,
            sum_amount=sum_amount,
            sd_price=sd_price,
            zpch_sum=zpch_sum,
            comment=comment,
            status=status,
            is_warranty=is_warranty,
        ),
    )
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


CLOSE_ROLES = ("owner", "branch_manager", "dispatcher")


@router.get("/{order_id}/close")
async def order_close_form(
    request: Request,
    order_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*CLOSE_ROLES)),
):
    order = orders_svc.get_order(db, order_id)
    if not order:
        return RedirectResponse("/admin/orders?error=notfound", status_code=302)
    master_ids = {order.assigned_to} if order.assigned_to else set()
    masters_map: dict[int, User] = {}
    if master_ids:
        from sqlalchemy import select
        masters_map = {
            master.tg_id: master
            for master in db.scalars(select(User).where(User.tg_id.in_(master_ids)))
        }
    decorated = _decorate(order, masters_map)
    return render(
        request,
        "order_close.html",
        user=user,
        active_page="orders",
        order=decorated,
    )


@router.post("/{order_id}/close")
async def order_close_submit(
    order_id: int,
    sum_amount: str | None = Form(None),
    paid_amount: str | None = Form(None),
    zpch_sum: str | None = Form(None),
    debt_amount: str | None = Form(None),
    debt_payment_date: str | None = Form(None),
    comment: str | None = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*CLOSE_ROLES)),  # noqa: ARG001
):
    order = orders_svc.get_order(db, order_id)
    if not order:
        return RedirectResponse("/admin/orders?error=notfound", status_code=302)

    def _safe_float(val: str | None) -> float | None:
        if not val or not val.strip():
            return None
        try:
            return float(val.strip())
        except ValueError:
            return None

    from promouters.services.financials import calculate_auto_debt

    payload: dict = {"status": "done_pending_sum"}
    parsed_sum = _safe_float(sum_amount)
    parsed_paid = _safe_float(paid_amount)
    parsed_zpch = _safe_float(zpch_sum)
    parsed_debt = _safe_float(debt_amount)

    if parsed_sum is not None:
        payload["sum_amount"] = parsed_sum
    if parsed_paid is not None:
        payload["paid_amount"] = parsed_paid
    if parsed_zpch is not None:
        payload["zpch_sum"] = parsed_zpch

    # Auto-compute debt if not explicitly provided
    if parsed_debt is not None:
        payload["debt_amount"] = parsed_debt
    elif parsed_sum is not None and parsed_paid is not None:
        auto_debt = calculate_auto_debt(parsed_sum, parsed_paid)
        if auto_debt > 0:
            payload["debt_amount"] = auto_debt

    if debt_payment_date and debt_payment_date.strip():
        try:
            payload["debt_payment_date"] = datetime.strptime(
                debt_payment_date.strip(), "%Y-%m-%d"
            )
        except ValueError:
            pass

    if comment and comment.strip():
        payload["comment"] = comment.strip()

    orders_svc.update_order(db, order, payload)
    return RedirectResponse("/admin/cash", status_code=302)


@router.post("/{order_id}/reject")
async def order_reject_submit(
    order_id: int,
    reason: str | None = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*CLOSE_ROLES)),  # noqa: ARG001
):
    """Reject an order — sets status to declined, zeroes financials, creates stat."""
    order = orders_svc.get_order(db, order_id)
    if not order:
        return RedirectResponse("/admin/orders?error=notfound", status_code=302)

    orders_svc.reject_order(db, order, reason=reason.strip() if reason and reason.strip() else None)
    return RedirectResponse(f"/admin/orders/{order_id}", status_code=302)
