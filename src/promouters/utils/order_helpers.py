"""Helpers ported from PythonProject2/handlers/utils.py and handlers/menu_kb.py.

Pure-Python lookups for the human-readable Russian names used in the PJ2
service-order UI. Kept dependency-free so any template/router can import it.
"""
from __future__ import annotations


EQUIP_TYPES: list[tuple[str, str]] = [
    ("ПК", "pc"),
    ("ТВ", "tv"),
    ("БТ", "appliance"),
    ("МНЧ", "handyman"),
    ("Другое", "other"),
]


STATUS_NAMES_RU: dict[str, str] = {
    "new": "Заявка создана",
    "assigned": "Назначена",
    "accepted": "Принята",
    "on_place": "В пути",
    "to_sd": "На СД",
    "done_pending_sum": "Ожидает приема кассы",
    "done": "Готова",
    "cancelled": "Отмена",
    "declined": "Отклонена",
    "completed": "Закрыта",
    "scheduled": "Запланирована",
}


def get_status_name_ru(status: str | None) -> str:
    if not status:
        return "—"
    return STATUS_NAMES_RU.get(status, status)


def get_equip_type_name(code: str | None) -> str:
    if not code:
        return "—"
    for name, equip_code in EQUIP_TYPES:
        if equip_code == code:
            return name
    return code


def get_equipment_category(equip_type: str | None) -> str:
    """Group an equip_type code into one of: appliance / digital / handyman / other."""
    if not equip_type:
        return "other"
    if equip_type in ("appliance", "washing_machine", "refrigerator", "oven", "dishwasher", "microwave"):
        return "appliance"
    if equip_type in ("pc", "laptop", "monitor", "phones", "tv", "tablet"):
        return "digital"
    if equip_type in ("handyman", "plumber", "electrician"):
        return "handyman"
    return "other"
