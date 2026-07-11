"""Расходы филиала (owner: полный доступ; ad_director: создание; branch_manager: просмотр).

Отдельный простой реестр расходов, не связанный с планами расходов (ExpensePlan).
"""
from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from promouters.core.config import get_settings
from promouters.db.session import get_db
from promouters.models.users import Branch, User
from promouters.schemas.branch_expenses import BranchExpenseCreate
from promouters.services import branch_expenses as svc
from promouters.services.access import is_owner
from promouters.web.deps import render, require_roles


logger = logging.getLogger(__name__)
router = APIRouter()

VIEW_ROLES = ("owner", "branch_manager", "ad_director")
CREATE_ROLES = ("owner", "ad_director")
MANAGE_ROLES = ("owner",)


def _parse_no_receipt(value: str) -> bool:
    return value.strip().lower() in {"on", "true", "1", "yes"}


def _list_branches(db: Session) -> list[Branch]:
    return list(db.scalars(select(Branch).order_by(Branch.name)))


@router.get("/")
async def expenses_list(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*VIEW_ROLES)),
):
    expenses = svc.list_expenses_for_actor(db, user)
    q = request.query_params
    flash_success = None
    if q.get("created"):
        flash_success = "Расход добавлен."
    elif q.get("updated"):
        flash_success = "Расход обновлён."
    elif q.get("deleted"):
        flash_success = "Расход удалён."
    role = user.role.code if user.role else None
    return render(
        request,
        "branch_expenses.html",
        user=user,
        active_page="branch_expenses",
        expenses=expenses,
        can_create=role in CREATE_ROLES,
        can_manage=role in MANAGE_ROLES,
        media_url=get_settings().media_url,
        flash_success=flash_success,
        flash_error="Расход не найден." if q.get("error") == "not-found" else None,
    )


@router.get("/new")
async def expense_create_form(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*CREATE_ROLES)),
):
    must_pick_branch = is_owner(user) or user.branch_id is None
    branches = _list_branches(db) if must_pick_branch else []
    return render(
        request,
        "branch_expense_create.html",
        user=user,
        active_page="branch_expenses",
        branches=branches,
        must_pick_branch=must_pick_branch,
        edit=False,
        action_url="/admin/branch-expenses/new",
        form={},
    )


@router.post("/new")
async def expense_create_submit(
    request: Request,
    topic: str = Form(...),
    amount: str = Form(...),
    no_receipt: str = Form(default=""),
    comment: str = Form(default=""),
    branch_id: str = Form(default=""),
    receipt: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*CREATE_ROLES)),
):
    must_pick_branch = is_owner(user) or user.branch_id is None

    def _render_error(message: str):
        return render(
            request,
            "branch_expense_create.html",
            user=user,
            active_page="branch_expenses",
            branches=_list_branches(db) if must_pick_branch else [],
            must_pick_branch=must_pick_branch,
            edit=False,
            action_url="/admin/branch-expenses/new",
            flash_error=message,
            form={
                "topic": topic,
                "amount": amount,
                "no_receipt": _parse_no_receipt(no_receipt),
                "comment": comment,
                "branch_id": branch_id,
            },
        )

    try:
        amount_dec = Decimal(amount.strip())
    except (InvalidOperation, ValueError, AttributeError):
        return _render_error("Сумма должна быть числом.")

    branch_uuid: UUID | None = None
    if branch_id.strip():
        try:
            branch_uuid = UUID(branch_id.strip())
        except ValueError:
            branch_uuid = None

    has_receipt = receipt is not None and bool(receipt.filename)
    content = await receipt.read() if has_receipt else None

    try:
        payload = BranchExpenseCreate(
            topic=topic,
            amount=amount_dec,
            no_receipt=_parse_no_receipt(no_receipt),
            comment=comment or None,
            branch_id=branch_uuid,
        )
    except Exception as exc:  # noqa: BLE001
        return _render_error(f"Проверьте поля: {exc}")

    try:
        svc.create_expense(
            db,
            user,
            payload,
            receipt_content=content,
            receipt_filename=receipt.filename if has_receipt else None,
            request=request,
        )
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.exception("branch_expense.create failed")
        message = str(getattr(exc, "detail", None) or exc) or "Не удалось создать расход."
        return _render_error(message)

    return RedirectResponse("/admin/branch-expenses?created=1", status_code=302)


def _load_expense(db: Session, expense_id: str):
    try:
        target_id = UUID(expense_id)
    except ValueError:
        return None
    try:
        return svc.get_expense_or_404(db, target_id)
    except Exception:  # noqa: BLE001
        return None


@router.get("/{expense_id}/edit")
async def expense_edit_form(
    request: Request,
    expense_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*MANAGE_ROLES)),
):
    expense = _load_expense(db, expense_id)
    if expense is None:
        return render(request, "404.html", user=user, status_code=404, what="Расход")
    return render(
        request,
        "branch_expense_create.html",
        user=user,
        active_page="branch_expenses",
        branches=[],
        must_pick_branch=False,
        edit=True,
        action_url=f"/admin/branch-expenses/{expense.id}/edit",
        form={
            "topic": expense.topic,
            "amount": expense.amount,
            "no_receipt": expense.no_receipt,
            "comment": expense.comment,
            "branch_id": str(expense.branch_id),
            "has_receipt": expense.receipt_path is not None,
        },
    )


@router.post("/{expense_id}/edit")
async def expense_edit_submit(
    request: Request,
    expense_id: str,
    topic: str = Form(...),
    amount: str = Form(...),
    no_receipt: str = Form(default=""),
    comment: str = Form(default=""),
    receipt: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*MANAGE_ROLES)),
):
    expense = _load_expense(db, expense_id)
    if expense is None:
        return RedirectResponse("/admin/branch-expenses?error=not-found", status_code=302)

    def _render_error(message: str):
        return render(
            request,
            "branch_expense_create.html",
            user=user,
            active_page="branch_expenses",
            branches=[],
            must_pick_branch=False,
            edit=True,
            action_url=f"/admin/branch-expenses/{expense.id}/edit",
            flash_error=message,
            form={
                "topic": topic,
                "amount": amount,
                "no_receipt": _parse_no_receipt(no_receipt),
                "comment": comment,
                "branch_id": str(expense.branch_id),
                "has_receipt": expense.receipt_path is not None,
            },
        )

    try:
        amount_dec = Decimal(amount.strip())
    except (InvalidOperation, ValueError, AttributeError):
        return _render_error("Сумма должна быть числом.")

    has_receipt = receipt is not None and bool(receipt.filename)
    content = await receipt.read() if has_receipt else None

    try:
        payload = BranchExpenseCreate(
            topic=topic,
            amount=amount_dec,
            no_receipt=_parse_no_receipt(no_receipt),
            comment=comment or None,
            branch_id=None,
        )
    except Exception as exc:  # noqa: BLE001
        return _render_error(f"Проверьте поля: {exc}")

    try:
        svc.update_expense(
            db,
            user,
            expense,
            payload,
            receipt_content=content,
            receipt_filename=receipt.filename if has_receipt else None,
            request=request,
        )
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.exception("branch_expense.update failed")
        message = str(getattr(exc, "detail", None) or exc) or "Не удалось обновить расход."
        return _render_error(message)

    return RedirectResponse("/admin/branch-expenses?updated=1", status_code=302)


@router.post("/{expense_id}/delete")
async def expense_delete(
    request: Request,
    expense_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*MANAGE_ROLES)),
):
    expense = _load_expense(db, expense_id)
    if expense is None:
        return RedirectResponse("/admin/branch-expenses?error=not-found", status_code=302)
    try:
        svc.delete_expense(db, user, expense, request=request)
    except Exception:  # noqa: BLE001
        db.rollback()
        logger.exception("branch_expense.delete failed")
        return RedirectResponse("/admin/branch-expenses?error=not-found", status_code=302)
    return RedirectResponse("/admin/branch-expenses?deleted=1", status_code=302)
