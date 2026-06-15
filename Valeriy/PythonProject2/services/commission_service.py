import json
import os
from typing import Dict, List, Tuple


DEFAULT_SETTINGS = {
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
    "phones": {  # ТВ и цифровые устройства (смартфоны отнесём сюда)
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
    "other": {  # Другое
        "title": "Другое",
        "tiers": [
            [0, None, 50],
        ],
    },
    "appliance": {  # Бытовая техника (крупная)
        "title": "Бытовая техника",
        "tiers": [
            [0, 9999, 40],
            [10000, 34999, 50],
            [35000, None, 60],
        ],
    },
}


SETTINGS_PATH = os.path.join("data", "commission_settings.json")


def _ensure_storage_dir():
    os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)


def load_settings() -> Dict[str, Dict]:
    _ensure_storage_dir()
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return DEFAULT_SETTINGS.copy()


def save_settings(settings: Dict[str, Dict]) -> None:
    _ensure_storage_dir()
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)


def get_category_for_type(equip_type_code: str) -> str:
    # Маппинг кодов типов на категории комиссий
    # codes: 'appliance', 'pc', 'phones', 'other'
    if equip_type_code in ("pc", "appliance", "phones", "other"):
        return equip_type_code
    # По умолчанию относить к 'other'
    return "other"


def get_master_pct(equip_type_code: str, net_amount: float) -> float:
    settings = load_settings()
    category = get_category_for_type(equip_type_code)
    conf = settings.get(category) or {}
    tiers: List[List] = conf.get("tiers") or []
    # Проходим по тиру в заданном порядке
    for lo, hi, pct in tiers:
        if net_amount >= (lo or 0) and (hi is None or net_amount <= hi):
            return float(pct)
    # Фолбэк, если не попало ни в один интервал
    # По умолчанию 50% для всех категорий
    return 50.0


