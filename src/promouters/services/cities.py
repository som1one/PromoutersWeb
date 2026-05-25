"""City CRUD ported from PythonProject2/admin_fastapi.py."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from promouters.models.service_ops import City


def list_cities(db: Session) -> list[City]:
    return list(db.scalars(select(City).order_by(City.name.asc())))


def get_city(db: Session, city_id: int) -> City | None:
    return db.get(City, city_id)


def create_city(
    db: Session,
    *,
    name: str,
    cash_company_percentage: float = 50.0,
    timezone: str = "Europe/Moscow",
) -> City:
    city = City(
        name=name.strip(),
        cash_company_percentage=cash_company_percentage,
        timezone=timezone,
    )
    db.add(city)
    db.commit()
    db.refresh(city)
    return city


def update_city(
    db: Session,
    city: City,
    *,
    name: str | None = None,
    cash_company_percentage: float | None = None,
    timezone: str | None = None,
) -> City:
    if name is not None:
        city.name = name.strip()
    if cash_company_percentage is not None:
        city.cash_company_percentage = cash_company_percentage
    if timezone is not None:
        city.timezone = timezone
    db.commit()
    db.refresh(city)
    return city


def delete_city(db: Session, city: City) -> None:
    db.delete(city)
    db.commit()
