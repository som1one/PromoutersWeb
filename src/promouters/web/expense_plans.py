"""Expense plans admin (owner / branch_manager)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from promouters.db.session import get_db
from promouters.models.finance import ExpensePlan
from promouters.models.users import User
from promouters.web.deps import render, require_roles


router = APIRouter()


@router.get("/")
async def expense_plans_list(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("owner", "branch_manager")),
):
    plans = list(
        db.scalars(
            select(ExpensePlan)
            .options(joinedload(ExpensePlan.branch), joinedload(ExpensePlan.created_by))
            .order_by(ExpensePlan.created_at.desc())
            .limit(200)
        )
    )
    return render(
        request,
        "expense_plans_list.html",
        user=user,
        active_page="expense_plans",
        plans=plans,
    )
