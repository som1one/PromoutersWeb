"""SD (сервисный документ) report (owner / director / dispatcher)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from promouters.db.session import get_db
from promouters.models.users import User
from promouters.services import sd as sd_svc
from promouters.services import cities as cities_svc
from promouters.web.deps import render, require_roles


router = APIRouter()


def _safe_int(value: str | int | None) -> int | None:
    if value is None or isinstance(value, int):
        return value
    s = str(value).strip()
    if not s:
        return None
    try:
        return int(s)
    except ValueError:
        return None


@router.get("/")
async def sd_view(
    request: Request,
    master_tg_id: str | None = None,
    city_id: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("owner", "director", "dispatcher")),
):
    resolved_city_id = _safe_int(city_id)
    resolved_master_tg_id = _safe_int(master_tg_id)
    report = sd_svc.sd_report(db, master_tg_id=resolved_master_tg_id, city_id=resolved_city_id)
    return render(
        request,
        "sd.html",
        user=user,
        active_page="sd",
        report=report,
        filter={"master_tg_id": resolved_master_tg_id, "city_id": resolved_city_id},
        available_cities=cities_svc.list_cities(db),
    )
