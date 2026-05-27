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
            qty = Decimal(form.get(f"item_{idx}_qty") or "0")
            price = Decimal(form.get(f"item_{idx}_price") or "0")
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
                                error="Заполните филиал и даты периода")

    items = _parse_items_from_form(form)
    if not items:
        return _back_with_error(request, db, user, plan=None,
                                error="Добавьте хотя бы одну строку расхода")

    payload = ExpensePlanCreate(
        title=(form.get("title") or "").strip() or "Без названия",
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
                                error=getattr(exc, "detail", str(exc)))
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
    items = _parse_items_from_form(form)
    payload = ExpensePlanUpdate(
        title=(form.get("title") or "").strip() or None,
        period_start=date.fromisoformat(form["period_start"]) if form.get("period_start") else None,
        period_end=date.fromisoformat(form["period_end"]) if form.get("period_end") else None,
        currency=(form.get("currency") or "RUB").upper(),
        comment=(form.get("comment") or "").strip() or None,
        items=items if items else None,
    )
    try:
        svc.update_plan(db, user, plan, payload, request=request)
    except Exception as exc:  # noqa: BLE001
        logger.exception("expense_plan.update failed")
        return _back_with_error(request, db, user, plan=plan,
                                error=getattr(exc, "detail", str(exc)))
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


def _back_with_error(request: Request, db: Session, user: User, *, plan, error: str):
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
    )
