"""Сервис плана расходов с маршрутом согласования у собственника."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from fastapi import HTTPException, Request, status
from sqlalchemy import Select, select
from sqlalchemy.orm import Session, joinedload, selectinload

from promouters.models.enums import ExpenseApprovalDecision, ExpensePlanStatus, RoleCode
from promouters.models.finance import ExpenseApproval, ExpensePlan, ExpensePlanItem
from promouters.models.users import Branch, User
from promouters.schemas.expense_plans import (
    ExpenseApprovalDecisionRequest,
    ExpenseApprovalRead,
    ExpensePlanCreate,
    ExpensePlanItemCreate,
    ExpensePlanItemRead,
    ExpensePlanRead,
    ExpensePlanUpdate,
)
from promouters.services.access import (
    ensure_same_branch,
    get_role_code,
    is_owner,
    require_branch_assignment,
)
from promouters.services.audit import write_audit_log
from promouters.services.notifications import (
    create_notification,
    notify_owners_about_key_change,
)

MONEY_QUANT = Decimal("0.01")


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def _full_name(user: User | None) -> str:
    if user is None:
        return ""
    full_name = " ".join(part for part in [user.first_name, user.last_name] if part).strip()
    return full_name or user.username


def expense_plan_query() -> Select[tuple[ExpensePlan]]:
    return (
        select(ExpensePlan)
        .options(
            joinedload(ExpensePlan.branch),
            joinedload(ExpensePlan.created_by),
            selectinload(ExpensePlan.items),
            selectinload(ExpensePlan.approvals).joinedload(ExpenseApproval.approver),
        )
    )


def to_item_read(item: ExpensePlanItem) -> ExpensePlanItemRead:
    return ExpensePlanItemRead(
        id=item.id,
        expense_plan_id=item.expense_plan_id,
        sequence=item.sequence,
        name=item.name,
        category=item.category,
        quantity=item.quantity,
        unit_price=item.unit_price,
        amount=item.amount,
        note=item.note,
    )


def to_approval_read(approval: ExpenseApproval) -> ExpenseApprovalRead:
    return ExpenseApprovalRead(
        id=approval.id,
        expense_plan_id=approval.expense_plan_id,
        approver_id=approval.approver_id,
        approver_name=_full_name(approval.approver),
        decision=approval.decision.value,
        comment=approval.comment,
        decided_at=approval.decided_at,
        created_at=approval.created_at,
    )


def to_plan_read(plan: ExpensePlan) -> ExpensePlanRead:
    return ExpensePlanRead(
        id=plan.id,
        branch_id=plan.branch_id,
        branch_name=plan.branch.name if plan.branch else "",
        created_by_id=plan.created_by_id,
        created_by_name=_full_name(plan.created_by),
        title=plan.title,
        period_start=plan.period_start,
        period_end=plan.period_end,
        total_amount=plan.total_amount,
        currency=plan.currency,
        status=plan.status.value,
        comment=plan.comment,
        submitted_at=plan.submitted_at,
        approved_at=plan.approved_at,
        items=[to_item_read(item) for item in sorted(plan.items, key=lambda i: i.sequence)],
        approvals=[to_approval_read(approval) for approval in plan.approvals],
        created_at=plan.created_at,
        updated_at=plan.updated_at,
    )


def get_plan_or_404(db: Session, plan_id: UUID) -> ExpensePlan:
    plan = db.scalar(expense_plan_query().where(ExpensePlan.id == plan_id))
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense plan not found")
    return plan


def _ensure_can_edit_branch(actor_user: User, branch_id: UUID) -> None:
    role_code = get_role_code(actor_user)
    if role_code == RoleCode.OWNER:
        return
    if role_code != RoleCode.BRANCH_MANAGER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only branch managers can manage expense plans",
        )
    ensure_same_branch(actor_user, branch_id)


def _ensure_view_access(actor_user: User, plan: ExpensePlan) -> None:
    role_code = get_role_code(actor_user)
    if role_code == RoleCode.OWNER:
        return
    if role_code in {RoleCode.BRANCH_MANAGER, RoleCode.AD_DIRECTOR}:
        ensure_same_branch(actor_user, plan.branch_id)
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")


def _calculate_items(items: list[ExpensePlanItemCreate]) -> tuple[list[ExpensePlanItem], Decimal]:
    persisted: list[ExpensePlanItem] = []
    total = Decimal("0.00")
    for item in items:
        amount = _quantize(item.unit_price * item.quantity)
        persisted.append(
            ExpensePlanItem(
                sequence=item.sequence,
                name=item.name.strip(),
                category=item.category.strip() if item.category else None,
                quantity=item.quantity,
                unit_price=item.unit_price,
                amount=amount,
                note=item.note,
            )
        )
        total += amount
    return persisted, _quantize(total)


def list_plans_for_actor(db: Session, actor_user: User) -> list[ExpensePlan]:
    stmt = expense_plan_query().order_by(ExpensePlan.created_at.desc())
    role_code = get_role_code(actor_user)

    if role_code == RoleCode.OWNER:
        pass
    elif role_code in {RoleCode.BRANCH_MANAGER, RoleCode.AD_DIRECTOR}:
        stmt = stmt.where(ExpensePlan.branch_id == require_branch_assignment(actor_user))
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    return list(db.scalars(stmt))


def create_plan(
    db: Session,
    actor_user: User,
    payload: ExpensePlanCreate,
    *,
    request: Request | None = None,
) -> ExpensePlan:
    _ensure_can_edit_branch(actor_user, payload.branch_id)

    if db.get(Branch, payload.branch_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Branch not found")

    if payload.period_end < payload.period_start:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="period_end must be greater or equal to period_start",
        )

    items, total = _calculate_items(payload.items)
    plan = ExpensePlan(
        branch_id=payload.branch_id,
        created_by_id=actor_user.id,
        title=payload.title.strip(),
        period_start=payload.period_start,
        period_end=payload.period_end,
        total_amount=total,
        currency=payload.currency.upper(),
        status=ExpensePlanStatus.DRAFT,
        comment=payload.comment,
    )
    db.add(plan)
    db.flush()

    for item in items:
        item.expense_plan_id = plan.id
        db.add(item)
    db.flush()

    created = get_plan_or_404(db, plan.id)
    write_audit_log(
        db,
        actor_user=actor_user,
        branch_id=created.branch_id,
        entity_type="expense_plan",
        entity_id=str(created.id),
        action="expense_plan.create",
        payload={"after": to_plan_read(created).model_dump(mode="json")},
        request=request,
    )
    notify_owners_about_key_change(
        db,
        actor_user=actor_user,
        title="Expense plan created",
        body=f"{_full_name(actor_user)} created expense plan '{created.title}'.",
        payload={"event": "expense_plan.create", "expense_plan_id": str(created.id)},
        branch_id=created.branch_id,
        request=request,
    )
    db.commit()
    return get_plan_or_404(db, plan.id)


def update_plan(
    db: Session,
    actor_user: User,
    plan: ExpensePlan,
    payload: ExpensePlanUpdate,
    *,
    request: Request | None = None,
) -> ExpensePlan:
    _ensure_can_edit_branch(actor_user, plan.branch_id)

    if plan.status not in {ExpensePlanStatus.DRAFT, ExpensePlanStatus.REJECTED}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="План в текущем статусе нельзя редактировать",
        )

    before = to_plan_read(plan).model_dump(mode="json")
    data = payload.model_dump(exclude_unset=True)

    if "title" in data and data["title"] is not None:
        plan.title = data["title"].strip()
    if "period_start" in data:
        plan.period_start = data["period_start"]
    if "period_end" in data:
        plan.period_end = data["period_end"]
    if plan.period_end < plan.period_start:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="period_end must be greater or equal to period_start",
        )
    if "currency" in data and data["currency"] is not None:
        plan.currency = data["currency"].upper()
    if "comment" in data:
        plan.comment = data["comment"]

    if "items" in data and data["items"] is not None:
        items, total = _calculate_items(payload.items or [])
        plan.items[:] = items
        plan.total_amount = total
        for item in plan.items:
            item.expense_plan_id = plan.id

    db.add(plan)
    db.flush()

    updated = get_plan_or_404(db, plan.id)
    write_audit_log(
        db,
        actor_user=actor_user,
        branch_id=updated.branch_id,
        entity_type="expense_plan",
        entity_id=str(updated.id),
        action="expense_plan.update",
        payload={"before": before, "after": to_plan_read(updated).model_dump(mode="json")},
        request=request,
    )
    db.commit()
    return get_plan_or_404(db, plan.id)


def submit_plan(
    db: Session,
    actor_user: User,
    plan: ExpensePlan,
    *,
    request: Request | None = None,
) -> ExpensePlan:
    _ensure_can_edit_branch(actor_user, plan.branch_id)

    if plan.status not in {ExpensePlanStatus.DRAFT, ExpensePlanStatus.REJECTED}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="План уже отправлен на согласование или закрыт",
        )
    if not plan.items:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Добавьте хотя бы одну строку расхода перед отправкой на согласование",
        )

    plan.status = ExpensePlanStatus.SUBMITTED
    plan.submitted_at = datetime.now(UTC)
    db.add(plan)
    db.flush()

    # Создаём запись согласования для каждого активного собственника
    owners_stmt = select(User).join(User.role).where(User.role.has(code=RoleCode.OWNER.value))
    owners = list(db.scalars(owners_stmt))
    for owner in owners:
        approval = ExpenseApproval(
            expense_plan_id=plan.id,
            approver_id=owner.id,
            decision=ExpenseApprovalDecision.PENDING,
        )
        db.add(approval)

        create_notification(
            db,
            user=owner,
            title="Expense plan submitted",
            body=(
                f"{_full_name(actor_user)} submitted expense plan '{plan.title}' "
                f"({plan.total_amount} {plan.currency}) for approval."
            ),
            payload={"event": "expense_plan.submitted", "expense_plan_id": str(plan.id)},
            actor_user=actor_user,
            branch_id=plan.branch_id,
            request=request,
        )

    write_audit_log(
        db,
        actor_user=actor_user,
        branch_id=plan.branch_id,
        entity_type="expense_plan",
        entity_id=str(plan.id),
        action="expense_plan.submit",
        payload={"total_amount": str(plan.total_amount), "currency": plan.currency},
        request=request,
    )
    db.commit()
    return get_plan_or_404(db, plan.id)


def decide_plan(
    db: Session,
    actor_user: User,
    plan: ExpensePlan,
    payload: ExpenseApprovalDecisionRequest,
    *,
    request: Request | None = None,
) -> ExpensePlan:
    if not is_owner(actor_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owners can approve expense plans",
        )

    if plan.status != ExpensePlanStatus.SUBMITTED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="План не на согласовании",
        )

    if payload.decision not in {
        ExpenseApprovalDecision.APPROVED,
        ExpenseApprovalDecision.REJECTED,
        ExpenseApprovalDecision.NEEDS_REVISION,
    }:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid decision",
        )

    approval = next(
        (item for item in plan.approvals if item.approver_id == actor_user.id),
        None,
    )
    if approval is None:
        approval = ExpenseApproval(
            expense_plan_id=plan.id,
            approver_id=actor_user.id,
            decision=payload.decision,
            comment=payload.comment,
            decided_at=datetime.now(UTC),
        )
        db.add(approval)
    else:
        approval.decision = payload.decision
        approval.comment = payload.comment
        approval.decided_at = datetime.now(UTC)
        db.add(approval)

    if payload.decision == ExpenseApprovalDecision.APPROVED:
        plan.status = ExpensePlanStatus.APPROVED
        plan.approved_at = datetime.now(UTC)
    elif payload.decision == ExpenseApprovalDecision.REJECTED:
        plan.status = ExpensePlanStatus.REJECTED
    elif payload.decision == ExpenseApprovalDecision.NEEDS_REVISION:
        plan.status = ExpensePlanStatus.DRAFT

    db.add(plan)
    db.flush()

    # Уведомляем автора плана
    if plan.created_by is not None:
        create_notification(
            db,
            user=plan.created_by,
            title=f"Expense plan {payload.decision.value}",
            body=(
                f"Owner {_full_name(actor_user)} returned decision '{payload.decision.value}' "
                f"for plan '{plan.title}'."
            ),
            payload={
                "event": "expense_plan.decision",
                "expense_plan_id": str(plan.id),
                "decision": payload.decision.value,
            },
            actor_user=actor_user,
            branch_id=plan.branch_id,
            request=request,
        )

    write_audit_log(
        db,
        actor_user=actor_user,
        branch_id=plan.branch_id,
        entity_type="expense_plan",
        entity_id=str(plan.id),
        action=f"expense_plan.decision.{payload.decision.value}",
        payload={"decision": payload.decision.value, "comment": payload.comment},
        request=request,
    )
    db.commit()
    return get_plan_or_404(db, plan.id)


def get_plan_for_actor(db: Session, actor_user: User, plan_id: UUID) -> ExpensePlan:
    plan = get_plan_or_404(db, plan_id)
    _ensure_view_access(actor_user, plan)
    return plan
