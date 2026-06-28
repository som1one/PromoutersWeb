"""Promoter routes admin (owner / branch_manager / ad_director / director)."""
from __future__ import annotations

import json
import logging
from datetime import date, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from promouters.core.config import Settings, get_settings
from promouters.db.session import get_db
from promouters.models.enums import RouteStatus, UserStatus
from promouters.models.finance import PayoutRate
from promouters.models.routing import Route
from promouters.models.users import Branch, Role, User
from promouters.schemas.routes import (
    RouteAssignRequest,
    RouteCreate,
    RoutePointInput,
    RouteUpdate,
)
from promouters.services import routes as svc
from promouters.web.deps import render, require_roles


logger = logging.getLogger(__name__)
router = APIRouter()

ROUTE_MANAGER_ROLES = ("owner", "branch_manager", "ad_director", "director")


def _list_branches(db: Session, user: User) -> list[Branch]:
    stmt = select(Branch).order_by(Branch.name)
    if user.role and user.role.code != "owner" and user.branch_id is not None:
        stmt = stmt.where(Branch.id == user.branch_id)
    return list(db.scalars(stmt))


def _list_promoters(db: Session, user: User) -> list[User]:
    stmt = (
        select(User)
        .options(joinedload(User.branch))
        .join(Role)
        .where(Role.code == "promoter")
        .where(User.status == UserStatus.ACTIVE)
        .order_by(User.last_name, User.first_name)
    )
    if user.role and user.role.code != "owner" and user.branch_id is not None:
        stmt = stmt.where(User.branch_id == user.branch_id)
    return list(db.scalars(stmt))


def _list_payout_rates(db: Session, user: User) -> list[PayoutRate]:
    stmt = select(PayoutRate).where(PayoutRate.is_active.is_(True)).order_by(PayoutRate.name)
    if user.role and user.role.code != "owner" and user.branch_id is not None:
        stmt = stmt.where(
            (PayoutRate.branch_id == user.branch_id) | (PayoutRate.branch_id.is_(None))
        )
    return list(db.scalars(stmt))


def _parse_points(raw: str) -> list[RoutePointInput]:
    try:
        data = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return []
    out: list[RoutePointInput] = []
    if not isinstance(data, list):
        return out
    # Фильтруем только точки с валидными координатами — без них маршрут не сохранится
    valid_items: list[dict] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        try:
            lat = float(item["latitude"])
            lng = float(item["longitude"])
        except (KeyError, TypeError, ValueError):
            continue
        item["latitude"] = lat
        item["longitude"] = lng
        valid_items.append(item)
    total = len(valid_items)
    for idx, item in enumerate(valid_items, start=1):
        # Принудительно выставляем start/finish крайним точкам — иначе валидатор сервиса
        # вернёт 422, даже если фронт случайно прислал checkpoint.
        if idx == 1:
            point_type = "start"
        elif idx == total:
            point_type = "finish"
        else:
            point_type = item.get("point_type") or "checkpoint"
            if point_type in ("start", "finish"):
                point_type = "checkpoint"
        try:
            out.append(RoutePointInput(
                sequence=idx,
                name=str(item.get("name") or "").strip() or f"Точка {idx}",
                address=item.get("address"),
                latitude=item["latitude"],
                longitude=item["longitude"],
                point_type=point_type,
                planned_arrival_at=None,
                notes=item.get("notes"),
            ))
        except (TypeError, ValueError):
            continue
    return out


def _serialize_points_for_form(points: list[RoutePointInput]) -> str:
    """Сериализовать точки обратно в JSON, чтобы вернуть форму с введёнными данными."""
    return json.dumps(
        [
            {
                "sequence": p.sequence,
                "name": p.name,
                "address": p.address,
                "latitude": p.latitude,
                "longitude": p.longitude,
                "point_type": p.point_type.value if hasattr(p.point_type, "value") else p.point_type,
                "notes": p.notes,
            }
            for p in points
        ],
        ensure_ascii=False,
    )


@router.get("/")
async def routes_list(
    request: Request,
    promoter_id: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*ROUTE_MANAGER_ROLES)),
):
    routes = svc.list_routes_for_actor(db, user)
    if promoter_id:
        try:
            promoter_uuid = UUID(promoter_id)
            routes = [r for r in routes if r.promoter_id == promoter_uuid]
        except ValueError:
            pass
    return render(
        request,
        "routes_list.html",
        user=user,
        active_page="routes",
        routes=routes,
    )


@router.get("/create")
async def route_create_form(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*ROUTE_MANAGER_ROLES)),
):
    branches = _list_branches(db, user)
    promoters = _list_promoters(db, user)
    rates = _list_payout_rates(db, user)
    return render(
        request,
        "route_form.html",
        user=user,
        active_page="routes",
        route=None,
        branches=branches,
        promoters=promoters,
        rates=rates,
        today=date.today().isoformat(),
    )


@router.post("/create")
async def route_create_submit(
    request: Request,
    title: str = Form(...),
    description: str = Form(default=""),
    work_date: str = Form(...),
    branch_id: str = Form(...),
    payout_rate_id: str = Form(default=""),
    promoter_id: str = Form(default=""),
    points_json: str = Form(default="[]"),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(require_roles(*ROUTE_MANAGER_ROLES)),
):
    points = _parse_points(points_json)
    # Сохраняем то, что прислал юзер, — чтобы вернуть форму с введёнными точками при ошибке
    submitted_points_json = _serialize_points_for_form(points) if points else points_json

    def _render_error(message: str):
        branches = _list_branches(db, user)
        promoters = _list_promoters(db, user)
        rates = _list_payout_rates(db, user)
        return render(
            request, "route_form.html",
            user=user, active_page="routes",
            route=None, branches=branches, promoters=promoters, rates=rates,
            today=date.today().isoformat(),
            points_json=submitted_points_json,
            flash_error=message,
        )

    if len(points) < 2:
        return _render_error(
            "Маршрут должен содержать минимум 2 точки с координатами (старт и финиш)."
        )

    try:
        payload = RouteCreate(
            title=title.strip(),
            description=description.strip() or None,
            work_date=date.fromisoformat(work_date),
            planned_start_at=None,
            planned_end_at=None,
            branch_id=UUID(branch_id),
            payout_rate_id=UUID(payout_rate_id) if payout_rate_id else None,
            promoter_id=UUID(promoter_id) if promoter_id else None,
            points=points,
        )
        new_route = svc.create_route(db, user, payload, settings, request=request)
    except Exception as exc:  # noqa: BLE001
        logger.exception("route.create failed")
        message = getattr(exc, "detail", None) or str(exc) or "Не удалось сохранить маршрут"
        return _render_error(str(message))
    return RedirectResponse(f"/admin/routes/{new_route.id}", status_code=302)


@router.get("/{route_id}")
async def route_detail(
    request: Request,
    route_id: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(require_roles(*ROUTE_MANAGER_ROLES, "promoter")),
):
    try:
        target_id = UUID(route_id)
    except ValueError:
        return render(request, "404.html", user=user, status_code=404, what="Маршрут")
    try:
        route = svc.get_route_for_actor(db, user, target_id)
    except Exception:  # noqa: BLE001
        return render(request, "404.html", user=user, status_code=404, what="Маршрут")
    branches = _list_branches(db, user)
    promoters = _list_promoters(db, user)
    rates = _list_payout_rates(db, user)
    points_json = json.dumps([
        {
            "sequence": p.sequence,
            "name": p.name,
            "address": p.address,
            "latitude": float(p.latitude) if p.latitude is not None else None,
            "longitude": float(p.longitude) if p.longitude is not None else None,
            "point_type": p.point_type.value if p.point_type else "checkpoint",
            "notes": p.notes,
        }
        for p in route.points
    ], ensure_ascii=False)
    return render(
        request,
        "route_form.html",
        user=user,
        active_page="routes",
        route=route,
        branches=branches,
        promoters=promoters,
        rates=rates,
        points_json=points_json,
        today=date.today().isoformat(),
    )


@router.post("/{route_id}/update")
async def route_update_submit(
    request: Request,
    route_id: str,
    title: str = Form(...),
    description: str = Form(default=""),
    work_date: str = Form(...),
    payout_rate_id: str = Form(default=""),
    points_json: str = Form(default="[]"),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(require_roles(*ROUTE_MANAGER_ROLES)),
):
    target_id = UUID(route_id)
    route = svc.get_route_for_actor(db, user, target_id)
    points = _parse_points(points_json)
    submitted_points_json = _serialize_points_for_form(points) if points else points_json

    def _render_error(message: str):
        return render(
            request, "route_form.html",
            user=user, active_page="routes",
            route=route,
            branches=_list_branches(db, user),
            promoters=_list_promoters(db, user),
            rates=_list_payout_rates(db, user),
            points_json=submitted_points_json,
            today=date.today().isoformat(),
            flash_error=message,
        )

    if len(points) < 2:
        return _render_error(
            "Маршрут должен содержать минимум 2 точки с координатами (старт и финиш)."
        )

    payload = RouteUpdate(
        title=title.strip() or None,
        description=description.strip() or None,
        work_date=date.fromisoformat(work_date) if work_date else None,
        payout_rate_id=UUID(payout_rate_id) if payout_rate_id else None,
        points=points,
    )
    try:
        svc.update_route(db, user, route, payload, settings, request=request)
    except Exception as exc:  # noqa: BLE001
        logger.exception("route.update failed")
        message = getattr(exc, "detail", None) or str(exc) or "Не удалось сохранить маршрут"
        return _render_error(str(message))
    return RedirectResponse(f"/admin/routes/{route_id}", status_code=302)


@router.post("/{route_id}/assign")
async def route_assign(
    request: Request,
    route_id: str,
    promoter_id: str = Form(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(require_roles(*ROUTE_MANAGER_ROLES)),
):
    target_id = UUID(route_id)
    route = svc.get_route_for_actor(db, user, target_id)
    try:
        svc.assign_route(
            db, user, route,
            RouteAssignRequest(promoter_id=UUID(promoter_id)),
            settings, request=request,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("route.assign failed")
    return RedirectResponse(f"/admin/routes/{route_id}", status_code=302)


@router.post("/{route_id}/cancel")
async def route_cancel(
    request: Request,
    route_id: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(require_roles(*ROUTE_MANAGER_ROLES)),
):
    target_id = UUID(route_id)
    route = svc.get_route_for_actor(db, user, target_id)
    try:
        svc.cancel_route(db, user, route, settings, request=request)
    except Exception:  # noqa: BLE001
        logger.exception("route.cancel failed")
    return RedirectResponse("/admin/routes", status_code=302)
