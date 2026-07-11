"""Расходы филиала — простой реестр расходов (тема + сумма + чек/комментарий).

Отдельная лёгкая сущность, не связанная с ExpensePlan. Права:
владелец — полный доступ; директор по рекламе — создание; руководитель филиала —
только просмотр (проверяется на уровне web-роутов через require_roles).
"""
from __future__ import annotations

import logging
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from promouters.core.config import get_settings
from promouters.models.finance import BranchExpense
from promouters.models.users import Branch, User
from promouters.schemas.branch_expenses import BranchExpenseCreate
from promouters.services.access import is_owner
from promouters.services.audit import write_audit_log


logger = logging.getLogger(__name__)

RECEIPT_OR_COMMENT_MSG = "Прикрепите чек или отметьте «без чека» и укажите комментарий."


def validate_receipt_or_comment(
    *, has_receipt: bool, no_receipt: bool, comment: str | None
) -> str | None:
    """Правило: расход валиден, если есть чек ИЛИ (отмечено «без чека» и есть комментарий)."""
    if has_receipt:
        return None
    if no_receipt and comment and comment.strip():
        return None
    return RECEIPT_OR_COMMENT_MSG


def _expense_query():
    return select(BranchExpense).options(
        joinedload(BranchExpense.branch),
        joinedload(BranchExpense.created_by),
    )


def get_expense_or_404(db: Session, expense_id: UUID) -> BranchExpense:
    expense = db.scalar(_expense_query().where(BranchExpense.id == expense_id))
    if expense is None:
        raise HTTPException(status_code=404, detail="Расход не найден")
    return expense


def list_expenses_for_actor(db: Session, actor_user: User) -> list[BranchExpense]:
    stmt = _expense_query().order_by(BranchExpense.created_at.desc())
    if not is_owner(actor_user) and actor_user.branch_id is not None:
        stmt = stmt.where(BranchExpense.branch_id == actor_user.branch_id)
    return list(db.scalars(stmt))


def save_expense_receipt_file(file_content: bytes, filename: str, expense_id: UUID | str) -> str:
    """Сохранить скрин чека на диск, вернуть относительный путь (отдаётся на /media/...)."""
    settings = get_settings()
    receipts_dir = Path(settings.media_root) / "expense_receipts"
    receipts_dir.mkdir(parents=True, exist_ok=True)
    ext = Path(filename).suffix.lower() or ".png"
    safe_name = f"{expense_id}{ext}"
    (receipts_dir / safe_name).write_bytes(file_content)
    return f"expense_receipts/{safe_name}"


def _resolve_branch(db: Session, actor_user: User, payload_branch_id: UUID | None) -> UUID:
    """Владелец (или пользователь без филиала) выбирает филиал; остальные — свой."""
    must_pick = is_owner(actor_user) or actor_user.branch_id is None
    if must_pick:
        if payload_branch_id is None:
            raise HTTPException(status_code=422, detail="Выберите филиал")
        if db.get(Branch, payload_branch_id) is None:
            raise HTTPException(status_code=404, detail="Филиал не найден")
        return payload_branch_id
    return actor_user.branch_id


def _audit_snapshot(expense: BranchExpense) -> dict:
    return {
        "topic": expense.topic,
        "amount": str(expense.amount),
        "currency": expense.currency,
        "no_receipt": expense.no_receipt,
        "has_receipt": expense.receipt_path is not None,
        "comment": expense.comment,
        "branch_id": str(expense.branch_id),
    }


def create_expense(
    db: Session,
    actor_user: User,
    payload: BranchExpenseCreate,
    *,
    receipt_content: bytes | None,
    receipt_filename: str | None,
    request: Request | None = None,
) -> BranchExpense:
    branch_id = _resolve_branch(db, actor_user, payload.branch_id)

    error = validate_receipt_or_comment(
        has_receipt=receipt_content is not None,
        no_receipt=payload.no_receipt,
        comment=payload.comment,
    )
    if error:
        raise HTTPException(status_code=422, detail=error)

    expense = BranchExpense(
        branch_id=branch_id,
        created_by_id=actor_user.id,
        topic=payload.topic,
        amount=payload.amount,
        currency=payload.currency,
        no_receipt=payload.no_receipt,
        comment=payload.comment,
    )
    db.add(expense)
    db.flush()

    if receipt_content is not None:
        expense.receipt_path = save_expense_receipt_file(
            receipt_content, receipt_filename or "receipt.png", expense.id
        )
        db.flush()

    write_audit_log(
        db,
        actor_user=actor_user,
        branch_id=branch_id,
        entity_type="branch_expense",
        entity_id=str(expense.id),
        action="branch_expense.create",
        payload={"after": _audit_snapshot(expense)},
        request=request,
    )
    db.commit()
    return get_expense_or_404(db, expense.id)


def update_expense(
    db: Session,
    actor_user: User,
    expense: BranchExpense,
    payload: BranchExpenseCreate,
    *,
    receipt_content: bytes | None,
    receipt_filename: str | None,
    request: Request | None = None,
) -> BranchExpense:
    if not is_owner(actor_user):
        raise HTTPException(status_code=403, detail="Недостаточно прав")

    before = _audit_snapshot(expense)

    expense.topic = payload.topic
    expense.amount = payload.amount
    expense.currency = payload.currency
    expense.no_receipt = payload.no_receipt
    expense.comment = payload.comment
    if receipt_content is not None:
        expense.receipt_path = save_expense_receipt_file(
            receipt_content, receipt_filename or "receipt.png", expense.id
        )

    error = validate_receipt_or_comment(
        has_receipt=expense.receipt_path is not None,
        no_receipt=expense.no_receipt,
        comment=expense.comment,
    )
    if error:
        raise HTTPException(status_code=422, detail=error)

    db.flush()
    write_audit_log(
        db,
        actor_user=actor_user,
        branch_id=expense.branch_id,
        entity_type="branch_expense",
        entity_id=str(expense.id),
        action="branch_expense.update",
        payload={"before": before, "after": _audit_snapshot(expense)},
        request=request,
    )
    db.commit()
    return get_expense_or_404(db, expense.id)


def delete_expense(
    db: Session,
    actor_user: User,
    expense: BranchExpense,
    *,
    request: Request | None = None,
) -> None:
    if not is_owner(actor_user):
        raise HTTPException(status_code=403, detail="Недостаточно прав")

    write_audit_log(
        db,
        actor_user=actor_user,
        branch_id=expense.branch_id,
        entity_type="branch_expense",
        entity_id=str(expense.id),
        action="branch_expense.delete",
        payload={"before": _audit_snapshot(expense)},
        request=request,
    )
    db.delete(expense)
    db.commit()
