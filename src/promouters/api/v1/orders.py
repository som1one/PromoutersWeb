"""Orders API endpoints — reject and close operations."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from promouters.db.session import get_db
from promouters.models.users import User
from promouters.services import orders as orders_svc
from promouters.services.financials import calculate_auto_debt, calculate_net_amount, calculate_shares, resolve_master_pct
from promouters.web.deps import require_roles


router = APIRouter(prefix="/orders", tags=["orders"])

ORDER_ROLES = ("owner", "director", "dispatcher", "branch_manager")


class RejectOrderRequest(BaseModel):
    reason: str | None = None


class CloseOrderRequest(BaseModel):
    sum_amount: float | None = None
    paid_amount: float | None = None
    zpch_sum: float | None = None
    debt_amount: float | None = None
    debt_payment_date: str | None = None
    comment: str | None = None


def _serialize_order(order: Any) -> dict[str, Any]:
    return {
        "id": order.id,
        "order_number": order.order_number,
        "status": order.status,
        "sum_amount": order.sum_amount,
        "paid_amount": order.paid_amount,
        "debt_amount": order.debt_amount,
        "zpch_sum": order.zpch_sum,
        "equip_type": order.equip_type,
        "assigned_to": order.assigned_to,
        "comment": order.comment,
    }


@router.post("/{order_id}/reject")
def reject_order_endpoint(
    order_id: int,
    body: RejectOrderRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*ORDER_ROLES)),  # noqa: ARG001
):
    """Reject an order from any status."""
    order = orders_svc.get_order(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    updated = orders_svc.reject_order(db, order, reason=body.reason)
    return {"status": "ok", "order": _serialize_order(updated)}


@router.post("/{order_id}/close")
def close_order_endpoint(
    order_id: int,
    body: CloseOrderRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*ORDER_ROLES)),  # noqa: ARG001
):
    """Close an order with financial data."""
    order = orders_svc.get_order(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    payload: dict[str, Any] = {"status": "done_pending_sum"}

    if body.sum_amount is not None:
        payload["sum_amount"] = body.sum_amount
    if body.paid_amount is not None:
        payload["paid_amount"] = body.paid_amount
    if body.zpch_sum is not None:
        payload["zpch_sum"] = body.zpch_sum

    # Auto-compute debt if not explicitly provided
    if body.debt_amount is not None:
        payload["debt_amount"] = body.debt_amount
    elif body.sum_amount is not None and body.paid_amount is not None:
        auto_debt = calculate_auto_debt(body.sum_amount, body.paid_amount)
        if auto_debt > 0:
            payload["debt_amount"] = auto_debt

    if body.comment:
        payload["comment"] = body.comment

    updated = orders_svc.update_order(db, order, payload)
    return {"status": "ok", "order": _serialize_order(updated)}
