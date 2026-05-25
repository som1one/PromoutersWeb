from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from promouters.models.enums import ExpenseApprovalDecision, ExpensePlanStatus


class ExpensePlanItemCreate(BaseModel):
    sequence: int = Field(default=1, ge=1)
    name: str = Field(min_length=1, max_length=255)
    category: str | None = Field(default=None, max_length=100)
    quantity: Decimal = Field(default=Decimal("1"), gt=0, decimal_places=2, max_digits=12)
    unit_price: Decimal = Field(ge=0, decimal_places=2, max_digits=12)
    note: str | None = None


class ExpensePlanItemRead(BaseModel):
    id: UUID
    expense_plan_id: UUID
    sequence: int
    name: str
    category: str | None
    quantity: Decimal
    unit_price: Decimal
    amount: Decimal
    note: str | None


class ExpensePlanCreate(BaseModel):
    title: str = Field(default="План расходов", min_length=1, max_length=255)
    branch_id: UUID
    period_start: date
    period_end: date
    currency: str = Field(default="RUB", min_length=3, max_length=3)
    comment: str | None = None
    items: list[ExpensePlanItemCreate] = Field(default_factory=list)


class ExpensePlanUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    period_start: date | None = None
    period_end: date | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    comment: str | None = None
    items: list[ExpensePlanItemCreate] | None = None


class ExpenseApprovalRead(BaseModel):
    id: UUID
    expense_plan_id: UUID
    approver_id: UUID
    approver_name: str
    decision: str
    comment: str | None
    decided_at: datetime | None
    created_at: datetime


class ExpenseApprovalDecisionRequest(BaseModel):
    decision: ExpenseApprovalDecision
    comment: str | None = None


class ExpensePlanRead(BaseModel):
    id: UUID
    branch_id: UUID
    branch_name: str
    created_by_id: UUID
    created_by_name: str
    title: str
    period_start: date
    period_end: date
    total_amount: Decimal
    currency: str
    status: str
    comment: str | None
    submitted_at: datetime | None
    approved_at: datetime | None
    items: list[ExpensePlanItemRead]
    approvals: list[ExpenseApprovalRead]
    created_at: datetime
    updated_at: datetime
