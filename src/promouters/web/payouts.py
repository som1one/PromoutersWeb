"""Payouts admin (owner / branch_manager)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from promouters.db.session import get_db
from promouters.models.finance import Payout
from promouters.models.users import User
from promouters.web.deps import render, require_roles


router = APIRouter()


@router.get("/")
async def payouts_list(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("owner", "branch_manager")),
):
    payouts = list(
        db.scalars(
            select(Payout)
            .options(joinedload(Payout.promoter), joinedload(Payout.approved_by))
            .order_by(Payout.created_at.desc())
            .limit(200)
        )
    )
    return render(
        request,
        "payouts_list.html",
        user=user,
        active_page="payouts",
        payouts=payouts,
    )
