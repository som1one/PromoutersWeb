"""Masters admin — list users with role=master, view detail."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from promouters.db.session import get_db
from promouters.models.users import Role, User
from promouters.web.deps import render, require_roles


router = APIRouter()


@router.get("/")
async def masters_list(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("owner", "director")),
):
    masters = list(
        db.scalars(
            select(User)
            .options(joinedload(User.role), joinedload(User.branch))
            .join(Role)
            .where(Role.code == "master")
            .order_by(User.last_name, User.first_name)
        )
    )
    return render(
        request,
        "masters.html",
        user=user,
        active_page="masters",
        masters=masters,
    )


@router.get("/{master_id}")
async def master_detail(
    request: Request,
    master_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("owner", "director")),
):
    from uuid import UUID
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
    return render(
        request,
        "master_card.html",
        user=user,
        active_page="masters",
        master=master,
    )
