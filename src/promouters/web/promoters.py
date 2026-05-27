"""Promoters admin — list users with role=promoter, scoped by branch.

Видят: owner (всех), branch_manager (своего филиала), ad_director (своего филиала).
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from promouters.db.session import get_db
from promouters.models.users import Role, User
from promouters.services.access import is_owner
from promouters.web.deps import render, require_roles


router = APIRouter()


@router.get("/")
async def promoters_list(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(
        require_roles("owner", "branch_manager", "ad_director", "director")
    ),
):
    stmt = (
        select(User)
        .options(joinedload(User.role), joinedload(User.branch))
        .join(Role)
        .where(Role.code == "promoter")
        .order_by(User.last_name, User.first_name)
    )
    if not is_owner(user) and user.branch_id is not None:
        stmt = stmt.where(User.branch_id == user.branch_id)
    promoters = list(db.scalars(stmt))
    return render(
        request,
        "promoters.html",
        user=user,
        active_page="promoters",
        promoters=promoters,
    )


@router.get("/{promoter_id}")
async def promoter_detail(
    request: Request,
    promoter_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(
        require_roles("owner", "branch_manager", "ad_director", "director")
    ),
):
    try:
        target_id = UUID(promoter_id)
    except ValueError:
        return render(request, "404.html", user=user, status_code=404, what="Промоутер")
    promoter = db.scalar(
        select(User)
        .options(joinedload(User.role), joinedload(User.branch))
        .where(User.id == target_id)
    )
    if not promoter:
        return render(request, "404.html", user=user, status_code=404, what="Промоутер")
    if not is_owner(user) and user.branch_id and promoter.branch_id != user.branch_id:
        return render(request, "forbidden.html", user=user, status_code=403)
    return render(
        request,
        "promoter_card.html",
        user=user,
        active_page="promoters",
        promoter=promoter,
    )
