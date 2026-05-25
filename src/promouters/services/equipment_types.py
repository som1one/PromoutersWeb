"""Equipment-type helpers ported from PythonProject2.

PJ2 uses a small hard-coded list of equipment codes (EQUIP_TYPES) that also
lives in ``equipment_types`` table, but for display/categorization the
hard-coded list is authoritative. We expose both.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from promouters.models.service_ops import EquipmentType
from promouters.utils.order_helpers import EQUIP_TYPES, get_equip_type_name


def list_equipment_types(db: Session) -> list[EquipmentType]:
    return list(db.scalars(select(EquipmentType).order_by(EquipmentType.name.asc())))


def equip_type_choices() -> list[tuple[str, str]]:
    """Return the (display_name, code) pairs used in PJ2 forms."""
    return list(EQUIP_TYPES)


__all__ = [
    "list_equipment_types",
    "equip_type_choices",
    "get_equip_type_name",
]
