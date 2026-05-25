"""Promoter routes admin (owner / branch_manager / ad_director)."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from promouters.db.session import get_db
from promouters.models.routing import Route
from promouters.models.users import User
from promouters.web.deps import render, require_roles


router = APIRouter()


@router.get("/")
async def routes_list(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("owner", "branch_manager", "ad_director")),
):
    routes = list(
        db.scalars(
            select(Route)
            .options(
                joinedload(Route.branch),
                joinedload(Route.promoter),
                joinedload(Route.created_by),
            )
            .order_by(Route.created_at.desc())
            .limit(200)
        )
    )
    return render(
        request,
        "routes_list.html",
        user=user,
        active_page="routes",
        routes=routes,
    )


@router.get("/{route_id}")
async def route_detail(
    request: Request,
    route_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("owner", "branch_manager", "ad_director")),
):
    try:
        target_id = UUID(route_id)
    except ValueError:
        return render(request, "404.html", user=user, status_code=404, what="Маршрут")
    route = db.scalar(
        select(Route)
        .options(
            joinedload(Route.branch),
            joinedload(Route.promoter),
            joinedload(Route.created_by),
            joinedload(Route.points),
        )
        .where(Route.id == target_id)
    )
    if not route:
        return render(request, "404.html", user=user, status_code=404, what="Маршрут")
    return render(
        request,
        "route_detail.html",
        user=user,
        active_page="routes",
        route=route,
    )
