"""Users admin (owner only)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from promouters.db.session import get_db
from promouters.models.users import Role, User
from promouters.web.deps import render, require_roles


router = APIRouter()


@router.get("/")
async def users_list(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("owner")),
):
    users = list(
        db.scalars(
            select(User)
            .options(joinedload(User.role), joinedload(User.branch))
            .order_by(User.created_at.desc())
        )
    )
    roles = list(db.scalars(select(Role).order_by(Role.name)))
    return render(
        request,
        "users.html",
        user=user,
        active_page="users",
        users=users,
        roles=roles,
    )


@router.get("/register")
async def user_register_form(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("owner")),
):
    roles = list(db.scalars(select(Role).order_by(Role.name)))
    return render(
        request,
        "register.html",
        user=user,
        active_page="users",
        roles=roles,
    )
