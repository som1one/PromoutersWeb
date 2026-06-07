from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from promouters.models.service_ops import SystemSettings
from promouters.schemas.company_profile import CompanyProfileData


SETTINGS_KEY = "company_profile"


def _get_row(db: Session) -> SystemSettings | None:
    return db.scalar(select(SystemSettings).where(SystemSettings.key == SETTINGS_KEY))


def load_profile(db: Session) -> CompanyProfileData:
    row = _get_row(db)
    if row and row.value:
        try:
            payload = json.loads(row.value)
            return CompanyProfileData.model_validate(payload)
        except Exception:  # noqa: BLE001
            pass
    return CompanyProfileData()


def save_profile(db: Session, profile: CompanyProfileData) -> CompanyProfileData:
    payload = profile.model_dump()
    row = _get_row(db)
    serialized = json.dumps(payload, ensure_ascii=False)
    if row is None:
        row = SystemSettings(
            key=SETTINGS_KEY,
            value=serialized,
            description="Company profile form payload",
        )
        db.add(row)
    else:
        row.value = serialized
    db.commit()
    return profile
