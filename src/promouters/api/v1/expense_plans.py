"""HTTP API для планов расходов и согласования."""

from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from promouters.api.deps import get_current_user
from promouters.db.session import get_db
from promouters.models.users import User
from promouters.schemas.expense_plans import (
    ExpenseApprovalDecisionRequest,
    ExpensePlanCreate,
    ExpensePlanRead,
    ExpensePlanUpdate,
)
from promouters.services.expense_plans import (
    create_plan,
    decide_plan,
    get_plan_for_actor,
    list_plans_for_actor,
    submit_plan,
    to_plan_read,
    update_plan,
)

router = APIRouter(prefix="/expense-plans", tags=["expense-plans"])


@router.get("", response_model=list[ExpensePlanRead])
def get_expense_plans(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ExpensePlanRead]:
    return [to_plan_read(plan) for plan in list_plans_for_actor(db, current_user)]


@router.post("", response_model=ExpensePlanRead, status_code=status.HTTP_201_CREATED)
def create_expense_plan_endpoint(
    payload: ExpensePlanCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ExpensePlanRead:
    return to_plan_read(create_plan(db, current_user, payload, request=request))


@router.get("/{plan_id}", response_model=ExpensePlanRead)
def get_expense_plan(
    plan_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ExpensePlanRead:
    plan = get_plan_for_actor(db, current_user, plan_id)
    return to_plan_read(plan)


@router.patch("/{plan_id}", response_model=ExpensePlanRead)
def update_expense_plan_endpoint(
    plan_id: UUID,
    payload: ExpensePlanUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ExpensePlanRead:
    plan = get_plan_for_actor(db, current_user, plan_id)
    return to_plan_read(update_plan(db, current_user, plan, payload, request=request))


@router.post("/{plan_id}/submit", response_model=ExpensePlanRead)
def submit_expense_plan_endpoint(
    plan_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ExpensePlanRead:
    plan = get_plan_for_actor(db, current_user, plan_id)
    return to_plan_read(submit_plan(db, current_user, plan, request=request))


@router.post("/{plan_id}/decision", response_model=ExpensePlanRead)
def decide_expense_plan_endpoint(
    plan_id: UUID,
    payload: ExpenseApprovalDecisionRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ExpensePlanRead:
    plan = get_plan_for_actor(db, current_user, plan_id)
    return to_plan_read(decide_plan(db, current_user, plan, payload, request=request))
