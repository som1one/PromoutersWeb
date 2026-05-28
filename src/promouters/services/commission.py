"""Commission tier config — DB-backed port of PythonProject2/services/commission_service.py.

PJ2 stored commission tiers in ``data/commission_settings.json``. We move them
to the shared ``system_settings`` table (key=``commission_config``) so the web
layer can read/write them from one source. PJ2 bots still read the JSON file
— admins changing tiers via the web won't affect bots until bots are ported.
"""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from promouters.models.service_ops import SystemSettings


SETTINGS_KEY = "commission_config"


DEFAULT_SETTINGS: dict[str, dict[str, Any]] = {
    "pc": {
        "title": "ПК и периферия",
        "tiers": [
            [0, 5999, 30],
            [6000, 8999, 35],
            [9000, 14999, 40],
            [15000, 24999, 45],
            [25000, 69999, 50],
            [70000, None, 60],
        ],
    },
    "phones": {
        "title": "ТВ и цифровые устройства",
        "tiers": [
            [0, 5999, 30],
            [6000, 9999, 40],
            [10000, 14999, 45],
            [15000, 34999, 50],
            [35000, 49999, 55],
            [50000, None, 60],
        ],
    },
    "other": {
        "title": "Другое",
        "tiers": [
            [0, None, 50],
        ],
    },
    "appliance": {
        "title": "Бытовая техника",
        "tiers": [
            [0, 9999, 40],
            [10000, 34999, 50],
            [35000, None, 60],
        ],
    },
}


def _get_row(db: Session) -> SystemSettings | None:
    return db.scalar(select(SystemSettings).where(SystemSettings.key == SETTINGS_KEY))


def load_settings(db: Session) -> dict[str, dict[str, Any]]:
    row = _get_row(db)
    if row and row.value:
        try:
            return json.loads(row.value)
        except json.JSONDecodeError:
            pass
    return {k: dict(v) for k, v in DEFAULT_SETTINGS.items()}


def save_settings(db: Session, settings: dict[str, dict[str, Any]]) -> None:
    row = _get_row(db)
    payload = json.dumps(settings, ensure_ascii=False)
    if row is None:
        row = SystemSettings(
            key=SETTINGS_KEY,
            value=payload,
            description="Commission tier configuration (JSON)",
        )
        db.add(row)
    else:
        row.value = payload
    db.commit()


def get_category_for_type(equip_type_code: str | None) -> str:
    if equip_type_code in ("pc", "appliance", "phones", "other"):
        return equip_type_code
    # Маппинг новых кодов из EQUIP_TYPES на существующие категории комиссий,
    # чтобы сохранённый commission_config продолжал работать без миграции.
    if equip_type_code == "tv":
        return "phones"
    if equip_type_code in ("handyman", "plumber", "electrician"):
        return "other"
    return "other"


def get_master_pct(db: Session, equip_type_code: str | None, net_amount: float) -> float:
    """Master commission % for a given equipment type and net amount.

    Mirrors PJ2's tier logic 1:1.
    """
    settings = load_settings(db)
    category = get_category_for_type(equip_type_code)
    conf = settings.get(category) or {}
    tiers: list[list[Any]] = conf.get("tiers") or []
    for tier in tiers:
        lo, hi, pct = tier[0], tier[1], tier[2]
        if net_amount >= (lo or 0) and (hi is None or net_amount <= hi):
            return float(pct)
    return 50.0
