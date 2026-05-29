"""Cities admin (owner only) — CRUD over PJ2 cities table."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from promouters.db.session import get_db
from promouters.models.users import User
from promouters.services import cities as cities_svc
from promouters.web.deps import render, require_roles


router = APIRouter()


@router.get("/")
async def cities_list(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("owner")),
):
    created = request.query_params.get("created")
    updated = request.query_params.get("updated")
    deleted = request.query_params.get("deleted")

    flash_success = None
    if created:
        flash_success = "Город создан."
    elif updated:
        flash_success = "Доля компании обновлена."
    elif deleted:
        flash_success = "Город удалён."

    return render(
        request,
        "cities.html",
        user=user,
        active_page="cities",
        cities=cities_svc.list_cities(db),
        flash_success=flash_success,
    )


@router.post("/")
async def city_create(
    request: Request,  # noqa: ARG001
    name: str = Form(...),
    cash_company_percentage: float = Form(50.0),
    timezone: str = Form("Europe/Moscow"),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("owner")),  # noqa: ARG001
):
    cities_svc.create_city(
        db,
        name=name,
        cash_company_percentage=cash_company_percentage,
        timezone=timezone,
    )
    return RedirectResponse("/admin/cities?created=1", status_code=302)


@router.post("/{city_id}/update")
async def city_update(
    city_id: int,
    name: str = Form(...),
    cash_company_percentage: float = Form(50.0),
    timezone: str = Form("Europe/Moscow"),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("owner")),  # noqa: ARG001
):
    city = cities_svc.get_city(db, city_id)
    if city:
        cities_svc.update_city(
            db, city,
            name=name,
            cash_company_percentage=cash_company_percentage,
            timezone=timezone,
        )
    return RedirectResponse("/admin/cities?updated=1", status_code=302)


@router.post("/{city_id}/delete")
async def city_delete(
    city_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("owner")),  # noqa: ARG001
):
    city = cities_svc.get_city(db, city_id)
    if city:
        cities_svc.delete_city(db, city)
    return RedirectResponse("/admin/cities?deleted=1", status_code=302)
