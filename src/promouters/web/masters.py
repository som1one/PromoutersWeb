"""Masters admin — list users with role=master, view detail and update legacy fields."""
from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from promouters.core.config import Settings, get_settings
from promouters.db.session import get_db
from promouters.models.users import Role, User
from promouters.services.access import is_owner
from promouters.web.deps import render, require_roles


router = APIRouter()


def _users_by_role(
    db: Session,
    actor: User,
    role_code: str,
) -> list[User]:
    from promouters.models.enums import UserStatus
    stmt = (
        select(User)
        .options(joinedload(User.role), joinedload(User.branch))
        .join(Role)
        .where(Role.code == role_code, User.status == UserStatus.ACTIVE)
        .order_by(User.last_name, User.first_name)
    )
    if not is_owner(actor) and actor.branch_id is not None:
        stmt = stmt.where(User.branch_id == actor.branch_id)
    return list(db.scalars(stmt))


def _get_master_for_actor(db: Session, actor: User, master_id: UUID) -> User | None:
    master = db.scalar(
        select(User)
        .options(joinedload(User.role), joinedload(User.branch))
        .join(Role)
        .where(User.id == master_id, Role.code == "master")
    )
    if master is None:
        return None
    if not is_owner(actor) and actor.branch_id and master.branch_id != actor.branch_id:
        return None
    return master


@router.get("/")
async def masters_list(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(
        require_roles("owner", "director", "branch_manager", "ad_director")
    ),
):
    masters = _users_by_role(db, user, "master")
    flash_success = None
    if request.query_params.get("updated"):
        flash_success = "Карточка мастера обновлена."
    return render(
        request,
        "masters.html",
        user=user,
        active_page="masters",
        masters=masters,
        flash_success=flash_success,
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
    master = _get_master_for_actor(db, user, target_id)
    if master is None:
        return render(request, "404.html", user=user, status_code=404, what="Мастер")
    return render(
        request,
        "master_card.html",
        user=user,
        active_page="masters",
        master=master,
    )


@router.post("/{master_id}/percentage")
async def master_update_percentage(
    master_id: str,
    master_percentage: float | None = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(
        require_roles("owner", "director", "branch_manager", "ad_director")
    ),
):
    try:
        target_id = UUID(master_id)
    except ValueError:
        return RedirectResponse("/admin/masters?error=notfound", status_code=302)
    master = _get_master_for_actor(db, user, target_id)
    if master is None:
        return RedirectResponse("/admin/masters?error=notfound", status_code=302)
    master.master_percentage = master_percentage
    db.add(master)
    db.commit()
    return RedirectResponse(f"/admin/masters/{master.id}?updated=1", status_code=302)


@router.post("/{master_id}/passport")
async def master_upload_passport(
    master_id: str,
    passport: UploadFile = File(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(
        require_roles("owner", "director", "branch_manager", "ad_director")
    ),
):
    try:
        target_id = UUID(master_id)
    except ValueError:
        return RedirectResponse("/admin/masters?error=notfound", status_code=302)
    master = _get_master_for_actor(db, user, target_id)
    if master is None:
        return RedirectResponse("/admin/masters?error=notfound", status_code=302)
    if not passport.filename:
        return RedirectResponse(f"/admin/masters/{master.id}?error=empty-file", status_code=302)

    safe_name = Path(passport.filename).name.replace(" ", "_")
    target_dir = Path(settings.media_root) / "masters" / str(master.id)
    target_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(safe_name).suffix or ".jpg"
    target_name = f"{uuid4().hex}{suffix}"
    target_path = target_dir / target_name
    target_path.write_bytes(await passport.read())

    master.passport_photo_path = str(Path("masters") / str(master.id) / target_name).replace("\\", "/")
    db.add(master)
    db.commit()
    return RedirectResponse(f"/admin/masters/{master.id}?updated=1", status_code=302)
