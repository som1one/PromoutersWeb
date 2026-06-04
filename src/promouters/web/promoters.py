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
from promouters.services.access import is_owner
from promouters.services.audit import write_audit_log
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

    before = {
        "id": str(promoter.id),
        "status": promoter.status.value,
        "first_name": promoter.first_name,
        "last_name": promoter.last_name,
        "branch_id": str(promoter.branch_id) if promoter.branch_id else None,
    }
    promoter.status = UserStatus.INACTIVE
    db.add(promoter)
    write_audit_log(
        db,
        actor_user=user,
        branch_id=promoter.branch_id,
        entity_type="user",
        entity_id=str(promoter.id),
        action="promoter.deactivate",
        payload={"before": before, "after": {**before, "status": UserStatus.INACTIVE.value}},
        request=request,
    )
    db.commit()
    return RedirectResponse("/admin/promoters", status_code=302)
