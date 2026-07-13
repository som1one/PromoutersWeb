"""Promoters admin — list users with role=promoter, scoped by branch.

Видят: owner (всех), branch_manager (своего филиала), ad_director (своего филиала).
"""
from __future__ import annotations

import logging
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from promouters.db.session import get_db
from promouters.models.enums import UserStatus
from promouters.models.service_ops import City
from promouters.models.users import Branch, Role, User
from promouters.schemas.users import UserCreate
from promouters.services import users as users_svc
from promouters.services.access import is_owner
from promouters.web.deps import render, require_roles


router = APIRouter()
logger = logging.getLogger(__name__)

# Создавать промоутеров может владелец, руководитель филиала и директор по рекламе.
# Директор по рекламе — ТОЛЬКО создавать (редактирование/удаление ему недоступны).
CREATE_ROLES = ("owner", "branch_manager", "ad_director")


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
    created = request.query_params.get("created")
    error_code = request.query_params.get("error")
    flash_success = None
    if created:
        flash_success = "Промоутер создан."
    elif deleted:
        flash_success = "Промоутер архивирован."
    return render(
        request,
        "promoters.html",
        user=user,
        active_page="promoters",
        promoters=promoters,
        can_create=user.role is not None and user.role.code in CREATE_ROLES,
        flash_success=flash_success,
        flash_error="Не удалось архивировать промоутера." if error_code == "delete-failed" else None,
    )


@router.get("/new")
async def promoter_create_form(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*CREATE_ROLES)),
):
    # Владелец и ad_director без филиала выбирают филиал вручную;
    # у остальных промоутер создаётся в их собственном филиале.
    must_pick_branch = is_owner(user) or user.branch_id is None
    branches = (
        list(db.scalars(select(Branch).order_by(Branch.name))) if must_pick_branch else []
    )
    cities = list(db.scalars(select(City).order_by(City.name)))
    return render(
        request,
        "promoter_create.html",
        user=user,
        active_page="promoters",
        branches=branches,
        cities=cities,
        must_pick_branch=must_pick_branch,
        form={},
    )


@router.post("/new")
async def promoter_create_submit(
    request: Request,
    first_name: str = Form(...),
    last_name: str = Form(...),
    tg_id: str = Form(default=""),
    phone: str = Form(default=""),
    city_id: str = Form(default=""),
    branch_id: str = Form(default=""),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*CREATE_ROLES)),
):
    must_pick_branch = is_owner(user) or user.branch_id is None

    def _render_error(message: str):
        branches = (
            list(db.scalars(select(Branch).order_by(Branch.name))) if must_pick_branch else []
        )
        cities = list(db.scalars(select(City).order_by(City.name)))
        return render(
            request,
            "promoter_create.html",
            user=user,
            active_page="promoters",
            branches=branches,
            cities=cities,
            must_pick_branch=must_pick_branch,
            flash_error=message,
            form={
                "first_name": first_name,
                "last_name": last_name,
                "tg_id": tg_id,
                "phone": phone,
                "city_id": city_id,
                "branch_id": branch_id,
            },
        )

    role = db.scalar(select(Role).where(Role.code == "promoter"))
    if role is None:
        return _render_error("Роль «промоутер» не найдена.")

    if must_pick_branch:
        branch_uuid: UUID | None = None
        if branch_id.strip():
            try:
                branch_uuid = UUID(branch_id.strip())
            except ValueError:
                branch_uuid = None
        if branch_uuid is None:
            return _render_error("Выберите филиал для промоутера.")
    else:
        branch_uuid = user.branch_id

    parsed_tg_id: int | None = None
    if tg_id.strip():
        try:
            parsed_tg_id = int(tg_id.strip())
        except ValueError:
            return _render_error("VK ID должен быть числом.")
    if parsed_tg_id is None:
        return _render_error("Укажите VK ID промоутера.")

    parsed_city_id: int | None = None
    if city_id.strip():
        try:
            parsed_city_id = int(city_id.strip())
        except ValueError:
            parsed_city_id = None

    # Промоутер работает через ВК-бота, а не через админку, поэтому
    # логин/почту/пароль генерируем автоматически.
    username = f"promoter_{uuid4().hex[:10]}"
    try:
        payload = UserCreate(
            username=username,
            email=f"{username}@promouters.local",
            phone=phone.strip() or None,
            password=uuid4().hex,
            first_name=first_name.strip(),
            last_name=last_name.strip(),
            middle_name=None,
            # Пишем VK ID и в tg_id (по нему назначаются заявки/уведомления
            # мастеров), и в vk_id — по нему бот промоутера находит человека
            # в первую очередь и может ему писать.
            tg_id=parsed_tg_id,
            vk_id=str(parsed_tg_id),
            status=UserStatus.ACTIVE,
            role_id=role.id,
            branch_id=branch_uuid,
            city_id=parsed_city_id,
        )
    except Exception as exc:  # noqa: BLE001
        return _render_error(f"Проверьте поля: {exc}")

    try:
        users_svc.create_user(db, user, payload, request=request)
    except Exception as exc:  # noqa: BLE001
        logger.exception("promoter.create failed")
        db.rollback()
        raw = str(getattr(exc, "detail", None) or exc)
        low = raw.lower()
        if "vk id" in low or "telegram" in low or "tg_id" in low:
            message = "Промоутер с таким VK ID уже существует."
        elif "phone" in low:
            message = "Промоутер с таким телефоном уже существует."
        elif "must be assigned to a branch" in low or "branch" in low:
            message = "Не удалось определить филиал промоутера — выберите филиал."
        else:
            message = raw or "Не удалось создать промоутера."
        return _render_error(message)

    return RedirectResponse("/admin/promoters?created=1", status_code=302)


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
        logger.exception("promoter.archive failed")
        db.rollback()
        return RedirectResponse("/admin/promoters?error=delete-failed", status_code=302)
    return RedirectResponse("/admin/promoters?deleted=1", status_code=302)
