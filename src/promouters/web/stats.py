"""Statistics dashboard (owner / branch_manager / ad_director / director / dispatcher)."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from promouters.db.session import get_db
from promouters.models.users import User
from promouters.services import cities as cities_svc
from promouters.services import statistics as stats_svc
from promouters.web.deps import render, require_roles


logger = logging.getLogger(__name__)
router = APIRouter()


def _empty_dashboard() -> dict:
    """Возвращает пустой каркас dashboard для случаев когда расчёт упал.

    Шаблон stats.html ожидает структуру с meta/cards/breakdowns; возвращаем
    нули и пустые списки, чтобы страница рендерилась.
    """
    return {
        "meta": {"date_from": None, "date_to": None, "period_days": 0,
                 "city_id": None, "city_name": "Все города", "master_id": None},
        "cards": {"completed": 0, "total": 0, "in_progress": 0, "refused": 0,
                  "gross_sum": 0.0, "net_sum": 0.0, "company_share": 0.0,
                  "avg_check": 0.0, "conversion": 0.0, "per_day": 0.0,
                  "cash_pending_sum": 0.0, "cash_pending_count": 0},
        "status_breakdown": [],
        "sources": [],
        "equipment": [],
        "masters": [],
        "cities": [],
        "daily": [],
        "cash_pending": {"count": 0, "company_sum": 0.0},
    }


@router.get("/")
async def stats_view(
    request: Request,
    period: str = "month",
    city_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(
        require_roles("owner", "branch_manager", "ad_director", "director", "dispatcher")
    ),
):
    df, dt = stats_svc.get_period_bounds(period)
    error_message: str | None = None
    try:
        dashboard = stats_svc.calculate_dashboard_stats(
            db, date_from=df, date_to=dt, city_id=city_id
        )
    except Exception:  # noqa: BLE001 — деградация лучше 500
        logger.exception("statistics.calculate_dashboard_stats failed")
        dashboard = _empty_dashboard()
        error_message = "Не удалось рассчитать статистику за выбранный период (нет данных или ошибка запроса)."

    try:
        available_cities = cities_svc.list_cities(db)
    except Exception:  # noqa: BLE001
        logger.exception("cities.list_cities failed")
        available_cities = []

    return render(
        request,
        "stats.html",
        user=user,
        active_page="stats",
        dashboard=dashboard,
        period=period,
        available_periods=stats_svc.PERIOD_PRESETS,
        available_cities=available_cities,
        filter={"city_id": city_id, "period": period},
        flash_error=error_message,
    )
