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


@router.get("/")
async def sd_view(
    request: Request,
    master_tg_id: int | None = None,
    city_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("owner", "director", "dispatcher")),
):
    report = sd_svc.sd_report(db, master_tg_id=master_tg_id, city_id=city_id)
    return render(
        request,
        "sd.html",
        user=user,
        active_page="sd",
        report=report,
        filter={"master_tg_id": master_tg_id, "city_id": city_id},
        available_cities=cities_svc.list_cities(db),
    )
