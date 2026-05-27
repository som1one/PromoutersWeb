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
from promouters.models.enums import RouteStatus
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
    for idx, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            continue
        try:
            out.append(RoutePointInput(
                sequence=int(item.get("sequence") or idx),
                name=str(item.get("name") or "").strip() or f"Точка {idx}",
                address=item.get("address"),
                latitude=float(item["latitude"]) if item.get("latitude") is not None else None,
                longitude=float(item["longitude"]) if item.get("longitude") is not None else None,
                point_type=item.get("point_type") or "checkpoint",
                planned_arrival_at=None,
                notes=item.get("notes"),
            ))
        except (TypeError, ValueError):
            continue
    return out


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
    points_json: str = Form(default="[]"),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(require_roles(*ROUTE_MANAGER_ROLES)),
):
    points = _parse_points(points_json)
    if len(points) < 2:
        branches = _list_branches(db, user)
        promoters = _list_promoters(db, user)
        rates = _list_payout_rates(db, user)
        return render(
            request, "route_form.html",
            user=user, active_page="routes",
            route=None, branches=branches, promoters=promoters, rates=rates,
            today=date.today().isoformat(),
            flash_error="Маршрут должен содержать минимум 2 точки (старт и финиш)",
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
            points=points,
        )
        new_route = svc.create_route(db, user, payload, settings, request=request)
    except Exception as exc:  # noqa: BLE001
        logger.exception("route.create failed")
        branches = _list_branches(db, user)
        promoters = _list_promoters(db, user)
        rates = _list_payout_rates(db, user)
        return render(
            request, "route_form.html",
            user=user, active_page="routes",
            route=None, branches=branches, promoters=promoters, rates=rates,
            today=date.today().isoformat(),
            flash_error=getattr(exc, "detail", str(exc)),
        )
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
    payload = RouteUpdate(
        title=title.strip() or None,
        description=description.strip() or None,
        work_date=date.fromisoformat(work_date) if work_date else None,
        payout_rate_id=UUID(payout_rate_id) if payout_rate_id else None,
        points=points if len(points) >= 2 else None,
    )
    try:
        svc.update_route(db, user, route, payload, settings, request=request)
    except Exception as exc:  # noqa: BLE001
        logger.exception("route.update failed")
        return RedirectResponse(f"/admin/routes/{route_id}?error={getattr(exc, 'detail', 'update')}", status_code=302)
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
