from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class BranchExpenseCreate(BaseModel):
    """Простой расход филиала: тема + сумма (+ чек ИЛИ «без чека» с комментарием)."""

    topic: str = Field(min_length=1, max_length=255)
    amount: Decimal = Field(gt=0, decimal_places=2, max_digits=12)
    currency: str = Field(default="RUB", min_length=3, max_length=3)
    no_receipt: bool = False
    comment: str | None = Field(default=None, max_length=2000)
    branch_id: UUID | None = None

    @field_validator("topic")
    @classmethod
    def strip_topic(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Тема расхода не может быть пустой")
        return stripped

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()

    @field_validator("comment")
    @classmethod
    def blank_comment_to_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None
