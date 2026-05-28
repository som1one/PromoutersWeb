"""Branches admin (owner only) — CRUD over the Branch model."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from promouters.db.session import get_db
from promouters.models.users import User
from promouters.schemas.branches import BranchCreate, BranchUpdate
from promouters.services import branches as branches_svc
from promouters.services import cities as cities_svc
from promouters.web.deps import render, require_roles


router = APIRouter()


def _city_options(db: Session) -> list[str]:
    """Названия городов из таблицы cities — для подсказок в форме филиала."""
    return [c.name for c in cities_svc.list_cities(db) if c.name]


@router.get("/")
async def branches_list(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("owner")),
):
    return render(
        request,
        "branches.html",
        user=user,
        active_page="branches",
        branches=branches_svc.list_branches(db),
        cities=_city_options(db),
        flash_error=request.query_params.get("error"),
        flash_success=request.query_params.get("ok"),
    )


@router.post("/")
async def branch_create(
    request: Request,
    name: str = Form(...),
    city: str = Form(default=""),
    address: str = Form(default=""),
    code: str = Form(default=""),
    is_active: str = Form(default="on"),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("owner")),
):
    payload = BranchCreate(
        name=name.strip(),
        code=code.strip() or None,
        city=city.strip() or None,
        address=address.strip() or None,
        is_active=(is_active == "on"),
    )
    try:
        branches_svc.create_branch(db, payload, actor_user=user, request=request)
    except HTTPException as exc:
        return RedirectResponse(
            f"/admin/branches?error={exc.detail}", status_code=303
        )
    return RedirectResponse("/admin/branches?ok=created", status_code=303)


@router.get("/{branch_id}/edit")
async def branch_edit_form(
    request: Request,
    branch_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("owner")),
):
    branch = branches_svc.get_branch_or_404(db, branch_id)
    return render(
        request,
        "branch_edit.html",
        user=user,
        active_page="branches",
        branch=branch,
        cities=_city_options(db),
        flash_error=request.query_params.get("error"),
    )


@router.post("/{branch_id}/edit")
async def branch_edit_submit(
    request: Request,
    branch_id: UUID,
    name: str = Form(...),
    city: str = Form(default=""),
    address: str = Form(default=""),
    code: str = Form(default=""),
    is_active: str = Form(default=""),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("owner")),
):
    branch = branches_svc.get_branch_or_404(db, branch_id)
    payload = BranchUpdate(
        name=name.strip(),
        code=code.strip() or None,
        city=city.strip() or None,
        address=address.strip() or None,
        is_active=(is_active == "on"),
    )
    try:
        branches_svc.update_branch(db, branch, payload, actor_user=user, request=request)
    except HTTPException as exc:
        return RedirectResponse(
            f"/admin/branches/{branch_id}/edit?error={exc.detail}", status_code=303
        )
    return RedirectResponse("/admin/branches?ok=updated", status_code=303)


@router.post("/{branch_id}/delete")
async def branch_delete(
    request: Request,
    branch_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("owner")),
):
    branch = branches_svc.get_branch_or_404(db, branch_id)
    try:
        branches_svc.delete_branch(db, branch, actor_user=user, request=request)
    except HTTPException as exc:
        # 409 — есть связанные пользователи/маршруты/выплаты
        msg = "У филиала есть связанные записи (пользователи, маршруты, выплаты и т.п.). Удаление невозможно."
        if exc.status_code != 409:
            msg = str(exc.detail)
        return RedirectResponse(f"/admin/branches?error={msg}", status_code=303)
    return RedirectResponse("/admin/branches?ok=deleted", status_code=303)
