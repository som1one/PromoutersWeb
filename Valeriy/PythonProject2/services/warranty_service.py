from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional


@dataclass(frozen=True)
class WarrantyInfo:
    days: int
    until: Optional[datetime]


def warranty_days_for_amount(amount: float) -> int:
    """
    Правила (как на скрине):
    - до 2999: 0 дней
    - 3000–5999: 14
    - 6000–8999: 30
    - 9000–14999: 60
    - 15000+: 90
    """
    try:
        amt = float(amount or 0)
    except Exception:
        amt = 0.0

    if amt <= 2999:
        return 0
    if 3000 <= amt <= 5999:
        return 14
    if 6000 <= amt <= 8999:
        return 30
    if 9000 <= amt <= 14999:
        return 60
    return 90


def compute_warranty(amount: float, closed_at: Optional[datetime] = None) -> WarrantyInfo:
    days = warranty_days_for_amount(amount)
    if days <= 0:
        return WarrantyInfo(days=0, until=None)
    if closed_at is None:
        closed_at = datetime.now(timezone.utc)
    # гарантируем tz-aware
    if closed_at.tzinfo is None:
        closed_at = closed_at.replace(tzinfo=timezone.utc)
    return WarrantyInfo(days=days, until=closed_at + timedelta(days=days))


def normalize_phone(phone: str) -> str:
    if not phone:
        return ""
    digits = "".join(ch for ch in str(phone) if ch.isdigit())
    # для РФ обычно важны последние 10 цифр
    return digits[-10:] if len(digits) >= 10 else digits


