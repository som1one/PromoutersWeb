"""Cash income report (owner / director)."""
from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from promouters.db.session import get_db
from promouters.models.users import User
from promouters.services import cash as cash_svc
from promouters.services import cities as cities_svc
from promouters.web.deps import render, require_roles


router = APIRouter()


@router.get("/")
async def cash_report(
    request: Request,
    city_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("owner", "director")),
):
    now = datetime.now()
    df = datetime.fromisoformat(date_from) if date_from else now.replace(day=1, hour=0, minute=0, second=0)
    dt = datetime.fromisoformat(date_to) if date_to else now.replace(hour=23, minute=59, second=59)
    report = cash_svc.calculate_cash_income(db, date_from=df, date_to=dt, city_id=city_id)
    return render(
        request,
        "cash.html",
        user=user,
        active_page="cash",
        report=report,
        filter={"city_id": city_id, "date_from": df.date().isoformat(), "date_to": dt.date().isoformat()},
        available_cities=cities_svc.list_cities(db),
    )
