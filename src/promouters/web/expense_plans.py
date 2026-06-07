"""Expense plans admin (owner / branch_manager) — list, create, edit, submit, decide."""
from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from uuid import UUID

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from promouters.db.session import get_db
from promouters.models.enums import ExpenseApprovalDecision
from promouters.models.users import Branch, User
from promouters.schemas.expense_plans import (
    ExpenseApprovalDecisionRequest,
    ExpensePlanCreate,
    ExpensePlanItemCreate,
    ExpensePlanUpdate,
)
from promouters.services import expense_plans as svc
from promouters.web.deps import render, require_roles


logger = logging.getLogger(__name__)
router = APIRouter()


def _parse_decimal(value: str | None) -> Decimal:
    raw = (value or "").strip().replace(" ", "").replace("\u00a0", "").replace(",", ".")
    if not raw:
        return Decimal("0")
    return Decimal(raw)


def _parse_items_from_form(form: dict[str, str]) -> list[ExpensePlanItemCreate]:
    """form fields: item_<idx>_name, item_<idx>_qty, item_<idx>_price, item_<idx>_category, item_<idx>_note"""
    indices = sorted({
        int(k.split("_")[1])
        for k in form.keys()
        if k.startswith("item_") and "_name" in k
    })
    out: list[ExpensePlanItemCreate] = []
    for seq, idx in enumerate(indices, start=1):
        name = (form.get(f"item_{idx}_name") or "").strip()
        if not name:
            continue
        try:
            qty = _parse_decimal(form.get(f"item_{idx}_qty"))
            price = _parse_decimal(form.get(f"item_{idx}_price"))
        except InvalidOperation:
            qty, price = Decimal("0"), Decimal("0")
        out.append(ExpensePlanItemCreate(
            sequence=seq,
            name=name,
            category=(form.get(f"item_{idx}_category") or "").strip() or None,
            quantity=qty,
            unit_price=price,
            note=(form.get(f"item_{idx}_note") or "").strip() or None,
        ))
    return out


def _parse_sheet_rows(raw_text: str | None) -> list[ExpensePlanItemCreate]:
    text = (raw_text or "").strip()
    if not text:
        return []

    items: list[ExpensePlanItemCreate] = []
    header_tokens = {
        "название", "наименование", "категория", "кол-во", "колво", "количество",
        "цена", "сумма", "комментарий", "заметка", "note",
        "name", "category", "qty", "quantity", "price", "amount", "comment",
    }
    for line_no, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        parts = [part.strip() for part in line.split("\t")]
        while parts and not parts[-1]:
            parts.pop()
        if not parts:
            continue

        normalized = {part.lower() for part in parts}
        if line_no == 1 and normalized and normalized.issubset(header_tokens):
            continue

        try:
            if len(parts) == 1:
                item = ExpensePlanItemCreate(sequence=len(items) + 1, name=parts[0], quantity=Decimal("1"), unit_price=Decimal("0"))
            elif len(parts) == 2:
                item = ExpensePlanItemCreate(sequence=len(items) + 1, name=parts[0], quantity=Decimal("1"), unit_price=_parse_decimal(parts[1]))
            elif len(parts) == 3:
                item = ExpensePlanItemCreate(
                    sequence=len(items) + 1,
                    name=parts[0],
                    category=parts[1] or None,
                    quantity=Decimal("1"),
                    unit_price=_parse_decimal(parts[2]),
                )
            else:
                item = ExpensePlanItemCreate(
                    sequence=len(items) + 1,
                    name=parts[0],
                    category=parts[1] or None,
                    quantity=_parse_decimal(parts[2] or "1"),
                    unit_price=_parse_decimal(parts[3]),
                    note=" | ".join(part for part in parts[4:] if part) or None,
                )
        except (InvalidOperation, ValueError) as exc:
            raise ValueError(f"Строка {line_no}: не удалось разобрать числа из таблицы") from exc

        items.append(item)
    return items


@router.get("/")
async def expense_plans_list(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("owner", "branch_manager")),
):
    plans = svc.list_plans_for_actor(db, user)
    return render(
        request,
        "expense_plans_list.html",
        user=user,
        active_page="expense_plans",
        plans=plans,
    )


@router.get("/create")
async def expense_plan_create_form(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("owner", "branch_manager")),
):
    branches = list(db.scalars(select(Branch).order_by(Branch.name)))
    return render(
        request,
        "expense_plan_form.html",
        user=user,
        active_page="expense_plans",
        plan=None,
        branches=branches,
        today=date.today().isoformat(),
        sheet_rows="",
    )


@router.post("/create")
async def expense_plan_create_submit(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("owner", "branch_manager")),
):
    form = dict(await request.form())
    try:
        branch_id = UUID(form.get("branch_id") or "")
        period_start = date.fromisoformat(form.get("period_start") or "")
        period_end = date.fromisoformat(form.get("period_end") or "")
    except (ValueError, TypeError):
        return _back_with_error(request, db, user, plan=None,
                                error="Заполните филиал и даты периода",
                                sheet_rows=form.get("sheet_rows") or "")

    try:
        sheet_items = _parse_sheet_rows(form.get("sheet_rows"))
    except ValueError as exc:
        return _back_with_error(request, db, user, plan=None, error=str(exc), sheet_rows=form.get("sheet_rows") or "")
    manual_items = _parse_items_from_form(form)
    items = sheet_items or manual_items

    payload = ExpensePlanCreate(
        title=(form.get("title") or "").strip() or "Черновик расходов",
        branch_id=branch_id,
        period_start=period_start,
        period_end=period_end,
        currency=(form.get("currency") or "RUB").upper(),
        comment=(form.get("comment") or "").strip() or None,
        items=items,
    )
    try:
        plan = svc.create_plan(db, user, payload, request=request)
    except Exception as exc:  # noqa: BLE001
        logger.exception("expense_plan.create failed")
        return _back_with_error(request, db, user, plan=None,
                                error=getattr(exc, "detail", str(exc)),
                                sheet_rows=form.get("sheet_rows") or "")
    return RedirectResponse(f"/admin/expense-plans/{plan.id}", status_code=302)


@router.get("/{plan_id}")
async def expense_plan_detail(
    request: Request,
    plan_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("owner", "branch_manager")),
):
    plan = svc.get_plan_for_actor(db, user, plan_id)
    branches = list(db.scalars(select(Branch).order_by(Branch.name)))
    return render(
        request,
        "expense_plan_form.html",
        user=user,
        active_page="expense_plans",
        plan=plan,
        branches=branches,
        sheet_rows="",
    )


@router.post("/{plan_id}")
async def expense_plan_update(
    request: Request,
    plan_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("owner", "branch_manager")),
):
    plan = svc.get_plan_for_actor(db, user, plan_id)
    form = dict(await request.form())
    try:
        sheet_items = _parse_sheet_rows(form.get("sheet_rows"))
    except ValueError as exc:
        return _back_with_error(request, db, user, plan=plan, error=str(exc), sheet_rows=form.get("sheet_rows") or "")
    manual_items = _parse_items_from_form(form)
    items = sheet_items or manual_items
    payload = ExpensePlanUpdate(
        title=(form.get("title") or "").strip() or None,
        period_start=date.fromisoformat(form["period_start"]) if form.get("period_start") else None,
        period_end=date.fromisoformat(form["period_end"]) if form.get("period_end") else None,
        currency=(form.get("currency") or "RUB").upper(),
        comment=(form.get("comment") or "").strip() or None,
        items=items,
    )
    try:
        svc.update_plan(db, user, plan, payload, request=request)
    except Exception as exc:  # noqa: BLE001
        logger.exception("expense_plan.update failed")
        return _back_with_error(request, db, user, plan=plan,
                                error=getattr(exc, "detail", str(exc)),
                                sheet_rows=form.get("sheet_rows") or "")
    return RedirectResponse(f"/admin/expense-plans/{plan.id}", status_code=302)


@router.post("/{plan_id}/submit")
async def expense_plan_submit(
    request: Request,
    plan_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("owner", "branch_manager")),
):
    plan = svc.get_plan_for_actor(db, user, plan_id)
    try:
        svc.submit_plan(db, user, plan, request=request)
    except Exception as exc:  # noqa: BLE001
        logger.exception("expense_plan.submit failed")
        return _back_with_error(request, db, user, plan=plan,
                                error=getattr(exc, "detail", str(exc)))
    return RedirectResponse(f"/admin/expense-plans/{plan.id}", status_code=302)


@router.post("/{plan_id}/decide")
async def expense_plan_decide(
    request: Request,
    plan_id: UUID,
    decision: str = Form(...),
    comment: str = Form(default=""),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("owner")),
):
    plan = svc.get_plan_for_actor(db, user, plan_id)
    try:
        decision_enum = ExpenseApprovalDecision(decision)
    except ValueError:
        return _back_with_error(request, db, user, plan=plan, error="Неизвестное решение")
    payload = ExpenseApprovalDecisionRequest(decision=decision_enum, comment=comment.strip() or None)
    try:
        svc.decide_plan(db, user, plan, payload, request=request)
    except Exception as exc:  # noqa: BLE001
        logger.exception("expense_plan.decide failed")
        return _back_with_error(request, db, user, plan=plan,
                                error=getattr(exc, "detail", str(exc)))
    return RedirectResponse(f"/admin/expense-plans/{plan.id}", status_code=302)


def _back_with_error(request: Request, db: Session, user: User, *, plan, error: str, sheet_rows: str = ""):
    branches = list(db.scalars(select(Branch).order_by(Branch.name)))
    return render(
        request,
        "expense_plan_form.html",
        user=user,
        active_page="expense_plans",
        plan=plan,
        branches=branches,
        flash_error=error,
        today=date.today().isoformat(),
        sheet_rows=sheet_rows,
    )
