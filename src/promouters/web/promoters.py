"""Promoters admin — list users with role=promoter, scoped by branch.

Видят: owner (всех), branch_manager (своего филиала), ad_director (своего филиала).
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from promouters.db.session import get_db
from promouters.models.enums import UserStatus
from promouters.models.users import Role, User
from promouters.services import users as users_svc
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
        .where(User.status == UserStatus.ACTIVE)
        .order_by(User.last_name, User.first_name)
    )
    if not is_owner(user) and user.branch_id is not None:
        stmt = stmt.where(User.branch_id == user.branch_id)
    promoters = list(db.scalars(stmt))
    deleted = request.query_params.get("deleted")
    error_code = request.query_params.get("error")
    return render(
        request,
        "promoters.html",
        user=user,
        active_page="promoters",
        promoters=promoters,
        flash_success="Промоутер архивирован." if deleted else None,
        flash_error="Не удалось архивировать промоутера." if error_code == "delete-failed" else None,
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


@router.post("/{promoter_id}/delete")
async def promoter_delete(
    request: Request,
    promoter_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("owner", "branch_manager")),
):
    try:
        target_id = UUID(promoter_id)
    except ValueError:
        return RedirectResponse("/admin/promoters?error=not-found", status_code=302)

    promoter = db.scalar(
        select(User)
        .options(joinedload(User.role), joinedload(User.branch))
        .join(Role)
        .where(User.id == target_id, Role.code == "promoter")
    )
    if promoter is None:
        return RedirectResponse("/admin/promoters?error=not-found", status_code=302)
    if not is_owner(user) and user.branch_id and promoter.branch_id != user.branch_id:
        return RedirectResponse("/admin/promoters?error=forbidden", status_code=302)

    try:
        users_svc.archive_user(db, user, promoter, request=request, action="promoter.archive")
    except Exception:  # noqa: BLE001
        return RedirectResponse("/admin/promoters?error=delete-failed", status_code=302)
    return RedirectResponse("/admin/promoters?deleted=1", status_code=302)
