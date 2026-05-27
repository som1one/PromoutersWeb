"""Masters & promoters admin — list users with role=master/promoter, view detail."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from promouters.db.session import get_db
from promouters.models.users import Role, User
from promouters.services.access import is_branch_manager, is_owner
from promouters.web.deps import render, require_roles


router = APIRouter()


def _users_by_role(
    db: Session,
    actor: User,
    role_code: str,
) -> list[User]:
    stmt = (
        select(User)
        .options(joinedload(User.role), joinedload(User.branch))
        .join(Role)
        .where(Role.code == role_code)
        .order_by(User.last_name, User.first_name)
    )
    # Cross-branch isolation: non-owner видят только свой филиал.
    if not is_owner(actor) and actor.branch_id is not None:
        stmt = stmt.where(User.branch_id == actor.branch_id)
    return list(db.scalars(stmt))


@router.get("/")
async def masters_list(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(
        require_roles("owner", "director", "branch_manager", "ad_director")
    ),
):
    masters = _users_by_role(db, user, "master")
    return render(
        request,
        "masters.html",
        user=user,
        active_page="masters",
        masters=masters,
        promoters=False,
    )


@router.get("/{master_id}")
async def master_detail(
    request: Request,
    master_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(
        require_roles("owner", "director", "branch_manager", "ad_director")
    ),
):
    try:
        target_id = UUID(master_id)
    except ValueError:
        return render(request, "404.html", user=user, status_code=404, what="Мастер")
    master = db.scalar(
        select(User)
        .options(joinedload(User.role), joinedload(User.branch))
        .where(User.id == target_id)
    )
    if not master:
        return render(request, "404.html", user=user, status_code=404, what="Мастер")
    if not is_owner(user) and user.branch_id and master.branch_id != user.branch_id:
        return render(request, "forbidden.html", user=user, status_code=403)
    return render(
        request,
        "master_card.html",
        user=user,
        active_page="masters",
        master=master,
    )
