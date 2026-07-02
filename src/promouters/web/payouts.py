"""Payouts admin (owner / branch_manager / ad_director)."""
from __future__ import annotations

import csv
import io
import logging
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from promouters.db.session import get_db
from promouters.models.enums import PayoutRateType, PayoutStatus
from promouters.models.users import User
from promouters.schemas.finance import PayoutCreate, PayoutListFilters
from promouters.services import finance as svc
from promouters.web.deps import render, require_roles


logger = logging.getLogger(__name__)
router = APIRouter()

VIEW_ROLES = ("owner", "branch_manager", "ad_director", "director")


def _filters_from_query(promoter_id: str | None, status_filter: str | None) -> PayoutListFilters:
    filters_data: dict = {}
    if promoter_id:
        try:
            filters_data["promoter_id"] = UUID(promoter_id)
        except ValueError:
            pass
    if status_filter:
        try:
            filters_data["status"] = PayoutStatus(status_filter)
        except ValueError:
            pass
    return PayoutListFilters(**filters_data)


@router.get("/")
async def payouts_list(
    request: Request,
    promoter_id: str | None = None,
    status_filter: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*VIEW_ROLES)),
):
    filters = _filters_from_query(promoter_id, status_filter)
    payouts = svc.list_payouts_raw_for_actor(db, user, filters=filters)
    summary = svc.summarize_payouts_by_promoter(payouts)

    # Stats counters
    total_count = len(payouts)
    pending_count = sum(1 for p in payouts if p.status == PayoutStatus.CALCULATED)
    paid_count = sum(1 for p in payouts if p.status == PayoutStatus.PAID)
    pending_sum = sum(float(p.amount or 0) for p in payouts if p.status == PayoutStatus.CALCULATED)
    paid_sum = sum(float(p.amount or 0) for p in payouts if p.status == PayoutStatus.PAID)
    total_sum = sum(float(p.amount or 0) for p in payouts)

    # Get promoters for "create payout" form
    all_users = list(db.scalars(select(User).order_by(User.first_name, User.last_name)))

    return render(
        request,
        "payouts_list.html",
        user=user,
        active_page="payouts",
        payouts=payouts,
        summary=summary,
        promoter_id=promoter_id or "",
        status_filter=status_filter or "",
        statuses=list(PayoutStatus),
        all_promoters=all_users,
        stats={
            "total_count": total_count,
            "pending_count": pending_count,
            "paid_count": paid_count,
            "pending_sum": pending_sum,
            "paid_sum": paid_sum,
            "total_sum": total_sum,
        },
    )


@router.post("/create")
async def payout_create(
    request: Request,
    promoter_id: str = Form(...),
    rate_type: str = Form(...),
    amount_per_unit: str = Form(...),
    units: str = Form(...),
    notes: str = Form(default=""),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("owner", "branch_manager")),
):
    """Create a manual payout from the admin form."""
    try:
        payload = PayoutCreate(
            promoter_id=UUID(promoter_id),
            rate_type=PayoutRateType(rate_type),
            amount_per_unit=Decimal(amount_per_unit.strip()),
            units=Decimal(units.strip()),
            notes=notes.strip() or None,
        )
        svc.create_manual_payout(db, user, payload, request=request)
    except Exception:  # noqa: BLE001
        logger.exception("payout.create failed")
    return RedirectResponse("/admin/payouts", status_code=302)


@router.post("/{payout_id}/approve")
async def payout_approve(
    request: Request,
    payout_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("owner", "branch_manager")),
):
    payout = svc.get_payout_or_404(db, UUID(payout_id))
    try:
        svc.approve_payout(db, user, payout, request=request)
    except Exception:  # noqa: BLE001
        logger.exception("payout.approve failed")
    return RedirectResponse("/admin/payouts", status_code=302)


@router.post("/{payout_id}/paid")
async def payout_mark_paid(
    request: Request,
    payout_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("owner", "branch_manager")),
):
    payout = svc.get_payout_or_404(db, UUID(payout_id))
    try:
        svc.mark_payout_paid(db, user, payout, request=request)
    except Exception:  # noqa: BLE001
        logger.exception("payout.mark_paid failed")
    return RedirectResponse("/admin/payouts", status_code=302)


@router.post("/{payout_id}/cancel")
async def payout_cancel(
    request: Request,
    payout_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("owner", "branch_manager")),
):
    payout = svc.get_payout_or_404(db, UUID(payout_id))
    try:
        svc.cancel_payout(db, user, payout, request=request)
    except Exception:  # noqa: BLE001
        logger.exception("payout.cancel failed")
    return RedirectResponse("/admin/payouts", status_code=302)


@router.get("/export.csv")
async def payouts_export_csv(
    request: Request,
    promoter_id: str | None = None,
    status_filter: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*VIEW_ROLES)),
):
    filters = _filters_from_query(promoter_id, status_filter)
    payouts = svc.list_payouts_raw_for_actor(db, user, filters=filters)
    buf = io.StringIO()
    buf.write("\ufeff")  # UTF-8 BOM для Excel
    writer = csv.writer(buf, delimiter=";")
    writer.writerow(["Промоутер", "Маршрут", "Тип", "Единиц", "Сумма", "Валюта", "Статус", "Рассчитано"])
    for p in payouts:
        promoter = f"{p.promoter.first_name} {p.promoter.last_name}" if p.promoter else "—"
        route = p.route.title if p.route else "—"
        rate_type = p.payout_rate.rate_type.value if p.payout_rate else "—"
        writer.writerow([
            promoter, route, rate_type,
            str(p.units or 0), str(p.amount or 0), p.currency,
            p.status.value if p.status else "—",
            p.calculated_at.strftime("%Y-%m-%d %H:%M") if p.calculated_at else "",
        ])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="payouts.csv"'},
    )
