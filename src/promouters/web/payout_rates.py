"""Payout rates management routes (owner / branch_manager)."""
from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation
from uuid import UUID

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from promouters.db.session import get_db
from promouters.models.enums import PayoutRateType
from promouters.models.users import Branch, User
from promouters.schemas.finance import PayoutRateCreate, PayoutRateUpdate
from promouters.services.finance import (
    create_payout_rate,
    get_payout_rate_or_404,
    list_payout_rates_for_actor,
    update_payout_rate,
)
from promouters.web.deps import render, require_roles


logger = logging.getLogger(__name__)
router = APIRouter()

RATE_MANAGER_ROLES = ("owner", "branch_manager")


def _list_branches(db: Session, user: User) -> list[Branch]:
    stmt = select(Branch).order_by(Branch.name)
    if user.role and user.role.code != "owner" and user.branch_id is not None:
        stmt = stmt.where(Branch.id == user.branch_id)
    return list(db.scalars(stmt))


@router.get("/")
async def payout_rates_list(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*RATE_MANAGER_ROLES)),
):
    rates = list_payout_rates_for_actor(db, user)
    return render(
        request,
        "payout_rates_list.html",
        user=user,
        active_page="payout_rates",
        rates=rates,
    )


@router.get("/create")
async def payout_rate_create_form(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*RATE_MANAGER_ROLES)),
):
    branches = _list_branches(db, user)
    return render(
        request,
        "payout_rate_form.html",
        user=user,
        active_page="payout_rates",
        rate=None,
        branches=branches,
    )


@router.post("/create")
async def payout_rate_create_submit(
    request: Request,
    name: str = Form(...),
    rate_type: str = Form(...),
    amount: str = Form(...),
    currency: str = Form(default="RUB"),
    branch_id: str = Form(default=""),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*RATE_MANAGER_ROLES)),
):
    def _render_error(message: str):
        branches = _list_branches(db, user)
        return render(
            request,
            "payout_rate_form.html",
            user=user,
            active_page="payout_rates",
            rate=None,
            branches=branches,
            flash_error=message,
        )

    try:
        amount_decimal = Decimal(amount)
    except (InvalidOperation, ValueError):
        return _render_error("Некорректная сумма.")

    try:
        parsed_rate_type = PayoutRateType(rate_type)
    except ValueError:
        return _render_error("Некорректный тип тарифа.")

    try:
        payload = PayoutRateCreate(
            name=name.strip(),
            rate_type=parsed_rate_type,
            amount=amount_decimal,
            currency=currency.strip() or "RUB",
            branch_id=UUID(branch_id) if branch_id else None,
        )
        create_payout_rate(db, user, payload, request=request)
    except Exception as exc:  # noqa: BLE001
        logger.exception("payout_rate.create failed")
        message = getattr(exc, "detail", None) or str(exc) or "Не удалось создать тариф"
        return _render_error(str(message))

    return RedirectResponse("/admin/payout-rates", status_code=302)


@router.get("/{rate_id}/edit")
async def payout_rate_edit_form(
    request: Request,
    rate_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*RATE_MANAGER_ROLES)),
):
    try:
        target_id = UUID(rate_id)
    except ValueError:
        return render(request, "404.html", user=user, status_code=404, what="Тариф")

    try:
        rate = get_payout_rate_or_404(db, target_id)
    except Exception:  # noqa: BLE001
        return render(request, "404.html", user=user, status_code=404, what="Тариф")

    branches = _list_branches(db, user)
    return render(
        request,
        "payout_rate_form.html",
        user=user,
        active_page="payout_rates",
        rate=rate,
        branches=branches,
    )


@router.post("/{rate_id}/update")
async def payout_rate_update_submit(
    request: Request,
    rate_id: str,
    name: str = Form(...),
    rate_type: str = Form(...),
    amount: str = Form(...),
    currency: str = Form(default="RUB"),
    branch_id: str = Form(default=""),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*RATE_MANAGER_ROLES)),
):
    try:
        target_id = UUID(rate_id)
    except ValueError:
        return render(request, "404.html", user=user, status_code=404, what="Тариф")

    try:
        rate = get_payout_rate_or_404(db, target_id)
    except Exception:  # noqa: BLE001
        return render(request, "404.html", user=user, status_code=404, what="Тариф")

    def _render_error(message: str):
        branches = _list_branches(db, user)
        return render(
            request,
            "payout_rate_form.html",
            user=user,
            active_page="payout_rates",
            rate=rate,
            branches=branches,
            flash_error=message,
        )

    try:
        amount_decimal = Decimal(amount)
    except (InvalidOperation, ValueError):
        return _render_error("Некорректная сумма.")

    try:
        parsed_rate_type = PayoutRateType(rate_type)
    except ValueError:
        return _render_error("Некорректный тип тарифа.")

    try:
        payload = PayoutRateUpdate(
            name=name.strip(),
            rate_type=parsed_rate_type,
            amount=amount_decimal,
            currency=currency.strip() or "RUB",
            branch_id=UUID(branch_id) if branch_id else None,
        )
        update_payout_rate(db, user, rate, payload, request=request)
    except Exception as exc:  # noqa: BLE001
        logger.exception("payout_rate.update failed")
        message = getattr(exc, "detail", None) or str(exc) or "Не удалось обновить тариф"
        return _render_error(str(message))

    return RedirectResponse("/admin/payout-rates", status_code=302)


@router.post("/{rate_id}/delete")
async def payout_rate_delete(
    request: Request,
    rate_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*RATE_MANAGER_ROLES)),
):
    try:
        target_id = UUID(rate_id)
    except ValueError:
        return RedirectResponse("/admin/payout-rates", status_code=302)

    try:
        rate = get_payout_rate_or_404(db, target_id)
        # Soft-delete: deactivate instead of removing from DB
        payload = PayoutRateUpdate(is_active=False)
        update_payout_rate(db, user, rate, payload, request=request)
    except Exception:  # noqa: BLE001
        logger.exception("payout_rate.delete failed")

    return RedirectResponse("/admin/payout-rates", status_code=302)
