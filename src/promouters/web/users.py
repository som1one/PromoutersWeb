"""Users admin (owner / branch_manager)."""
from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from promouters.db.session import get_db
from promouters.models.enums import UserStatus
from promouters.models.users import Branch, Role, User
from promouters.schemas.users import UserCreate, UserUpdate
from promouters.services import users as users_svc
from promouters.services.access import is_branch_manager, is_owner
from promouters.web.deps import render, require_roles


logger = logging.getLogger(__name__)
router = APIRouter()


def _flash_success_redirect(target: str) -> RedirectResponse:
    return RedirectResponse(target, status_code=302)


def _filter_users(
    db: Session,
    actor: User,
    *,
    role_code: str | None,
    branch_id: str | None,
    search: str | None,
) -> list[User]:
    stmt = (
        select(User)
        .options(joinedload(User.role), joinedload(User.branch))
        .order_by(User.created_at.desc())
    )
    if not is_owner(actor) and is_branch_manager(actor) and actor.branch_id is not None:
        stmt = stmt.where(User.branch_id == actor.branch_id)
    if role_code:
        stmt = stmt.join(User.role).where(Role.code == role_code)
    if branch_id:
        try:
            stmt = stmt.where(User.branch_id == UUID(branch_id))
        except ValueError:
            pass
    if search:
        s = f"%{search.strip()}%"
        from sqlalchemy import or_
        stmt = stmt.where(
            or_(
                User.first_name.ilike(s),
                User.last_name.ilike(s),
                User.username.ilike(s),
                User.email.ilike(s),
                User.phone.ilike(s),
            )
        )
    return list(db.scalars(stmt))


@router.get("/")
async def users_list(
    request: Request,
    role_code: str | None = None,
    branch_id: str | None = None,
    search: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("owner", "branch_manager")),
):
    users = _filter_users(db, user, role_code=role_code, branch_id=branch_id, search=search)
    roles = list(db.scalars(select(Role).order_by(Role.name)))
    branches = list(db.scalars(select(Branch).order_by(Branch.name)))
    return render(
        request,
        "users.html",
        user=user,
        active_page="users",
        users=users,
        roles=roles,
        branches=branches,
        filter={"role_code": role_code or "", "branch_id": branch_id or "", "search": search or ""},
    )


@router.get("/register")
async def user_register_form(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("owner", "branch_manager")),
):
    roles = list(db.scalars(select(Role).order_by(Role.name)))
    branches = list(db.scalars(select(Branch).order_by(Branch.name)))
    return render(
        request,
        "register.html",
        user=user,
        active_page="users",
        roles=roles,
        branches=branches,
    )


@router.post("/register")
async def user_register_submit(
    request: Request,
    first_name: str = Form(...),
    last_name: str = Form(...),
    phone: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    role_code: str = Form(...),
    username: str = Form(...),
    branch_id: str = Form(default=""),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("owner", "branch_manager")),
):
    role = db.scalar(select(Role).where(Role.code == role_code))
    if role is None:
        roles = list(db.scalars(select(Role).order_by(Role.name)))
        branches = list(db.scalars(select(Branch).order_by(Branch.name)))
        return render(
            request,
            "register.html",
            user=user,
            active_page="users",
            roles=roles,
            branches=branches,
            flash_error="Роль не найдена",
        )

    branch_uuid: UUID | None = None
    if branch_id:
        try:
            branch_uuid = UUID(branch_id)
        except ValueError:
            branch_uuid = None

    payload = UserCreate(
        username=username.strip(),
        email=email.strip(),
        phone=phone.strip(),
        password=password,
        first_name=first_name.strip(),
        last_name=last_name.strip(),
        middle_name=None,
        status=UserStatus.ACTIVE,
        role_id=role.id,
        branch_id=branch_uuid,
    )
    try:
        users_svc.create_user(db, user, payload, request=request)
    except Exception as exc:  # noqa: BLE001
        logger.exception("user.create failed")
        roles = list(db.scalars(select(Role).order_by(Role.name)))
        branches = list(db.scalars(select(Branch).order_by(Branch.name)))
        message = getattr(exc, "detail", None) or str(exc) or "Не удалось создать пользователя"
        return render(
            request,
            "register.html",
            user=user,
            active_page="users",
            roles=roles,
            branches=branches,
            flash_error=str(message),
        )
    return _flash_success_redirect("/admin/users")


@router.get("/{user_id}")
async def user_detail(
    request: Request,
    user_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("owner", "branch_manager")),
):
    target = users_svc.get_user_for_actor(db, user, user_id)
    roles = list(db.scalars(select(Role).order_by(Role.name)))
    branches = list(db.scalars(select(Branch).order_by(Branch.name)))
    return render(
        request,
        "user_edit.html",
        user=user,
        active_page="users",
        target=target,
        roles=roles,
        branches=branches,
    )


@router.post("/{user_id}")
async def user_update(
    request: Request,
    user_id: UUID,
    first_name: str = Form(...),
    last_name: str = Form(...),
    phone: str = Form(...),
    email: str = Form(...),
    role_code: str = Form(...),
    branch_id: str = Form(default=""),
    status_code: str = Form(default="active"),
    password: str = Form(default=""),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("owner", "branch_manager")),
):
    target = users_svc.get_user_for_actor(db, user, user_id)
    role = db.scalar(select(Role).where(Role.code == role_code))
    if role is None:
        return RedirectResponse(f"/admin/users/{user_id}?error=role-not-found", status_code=302)

    branch_uuid: UUID | None = None
    if branch_id:
        try:
            branch_uuid = UUID(branch_id)
        except ValueError:
            branch_uuid = None

    update_data: dict = {
        "first_name": first_name.strip(),
        "last_name": last_name.strip(),
        "phone": phone.strip(),
        "email": email.strip(),
        "role_id": role.id,
        "branch_id": branch_uuid,
        "status": UserStatus(status_code) if status_code in UserStatus.__members__.values() or status_code in [s.value for s in UserStatus] else UserStatus.ACTIVE,
    }
    if password:
        update_data["password"] = password

    payload = UserUpdate(**update_data)
    try:
        users_svc.update_user(db, user, target, payload, request=request)
    except Exception as exc:  # noqa: BLE001
        logger.exception("user.update failed")
        roles = list(db.scalars(select(Role).order_by(Role.name)))
        branches = list(db.scalars(select(Branch).order_by(Branch.name)))
        message = getattr(exc, "detail", None) or str(exc) or "Не удалось сохранить"
        return render(
            request,
            "user_edit.html",
            user=user,
            active_page="users",
            target=target,
            roles=roles,
            branches=branches,
            flash_error=str(message),
        )
    return RedirectResponse("/admin/users", status_code=302)


@router.post("/{user_id}/delete")
async def user_delete(
    request: Request,
    user_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("owner")),
):
    target = users_svc.get_user_for_actor(db, user, user_id)
    try:
        users_svc.delete_user(db, user, target, request=request)
    except Exception:  # noqa: BLE001
        logger.exception("user.delete failed")
    return RedirectResponse("/admin/users", status_code=302)
