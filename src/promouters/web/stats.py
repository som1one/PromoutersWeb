"""Statistics dashboard (owner / director)."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from promouters.db.session import get_db
from promouters.models.users import User
from promouters.services import cities as cities_svc
from promouters.services import statistics as stats_svc
from promouters.web.deps import render, require_roles


router = APIRouter()


@router.get("/")
async def stats_view(
    request: Request,
    period: str = "month",
    city_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("owner", "director")),
):
    df, dt = stats_svc.get_period_bounds(period)
    dashboard = stats_svc.calculate_dashboard_stats(db, date_from=df, date_to=dt, city_id=city_id)
    return render(
        request,
        "stats.html",
        user=user,
        active_page="stats",
        dashboard=dashboard,
        period=period,
        available_periods=stats_svc.PERIOD_PRESETS,
        available_cities=cities_svc.list_cities(db),
        filter={"city_id": city_id, "period": period},
    )
