"""Pure financial calculation functions for the orders module.

Extracted from cash.py/statistics.py to provide a single source of truth for:
- Net amount calculation (excludes sd_price, only subtracts zpch_sum)
- Commission resolution (individual % → tiered config → default)
- Share splitting (company vs master)
- Auto-debt calculation
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from promouters.models.users import User
from promouters.services.commission import get_master_pct


def calculate_net_amount(sum_amount: float | None, zpch_sum: float | None) -> float:
    """Compute net_amount = max(sum_amount - zpch_sum, 0).

    sd_price is intentionally excluded from this calculation.
    None values are treated as zero.
    """
    s = float(sum_amount or 0)
    z = float(zpch_sum or 0)
    return round(max(s - z, 0.0), 2)


def calculate_shares(
    net_amount: float, master_pct: float
) -> tuple[float, float]:
    """Return (company_share, master_share) rounded to 2 decimal places.

    company_share = net_amount * (100 - master_pct) / 100
    master_share  = net_amount * master_pct / 100
    """
    master_share = round(net_amount * master_pct / 100.0, 2)
    company_share = round(net_amount * (100.0 - master_pct) / 100.0, 2)
    return company_share, master_share


def calculate_auto_debt(
    sum_amount: float | None, paid_amount: float | None
) -> float:
    """Auto-compute debt_amount when not explicitly provided.

    debt_amount = max(sum_amount - paid_amount, 0)
    """
    s = float(sum_amount or 0)
    p = float(paid_amount or 0)
    return round(max(s - p, 0.0), 2)


def resolve_master_pct(
    db: Session,
    *,
    master: User | None,
    equip_type: str | None,
    net_amount: float,
    is_warranty: bool = False,
) -> float:
    """Resolve master commission percentage using hybrid logic.

    Priority order:
    1. Warranty orders → always 50%
    2. master.master_percentage (if non-null) → use individual value
    3. commission_config tier lookup by equip_type + net_amount
    4. Default fallback → 50%
    """
    if is_warranty:
        return 50.0
    if master is not None and master.master_percentage is not None:
        return float(master.master_percentage)
    try:
        return float(get_master_pct(db, equip_type, net_amount))
    except Exception:
        return 50.0
