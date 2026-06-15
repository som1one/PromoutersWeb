"""Seed PythonProject2-side demo data on top of seed_demo_data.py.

Adds:
- ``dispatcher.demo`` and ``director.pj2`` accounts (new role codes)
- tg_id assignments for existing demo users so PJ2 order FKs resolve
- 3 cities, 4 equipment types
- ``commission_config`` row in ``system_settings``
- ~6 service orders across different statuses, plus a couple of stats rows

Run AFTER ``scripts/seed_demo_data.py``.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from promouters.db.session import SessionLocal
from promouters.models.service_ops import (
    City,
    EquipmentType,
    Order,
    Stat,
    SystemSettings,
)
from promouters.models.users import Role, User
from promouters.services.commission import DEFAULT_SETTINGS, SETTINGS_KEY
from promouters.utils.passwords import hash_password


DEFAULT_PASSWORD = "demo12345"
NOW = datetime.now(timezone.utc)


TG_IDS = {
    "owner.demo": 100001,
    "director.center": 100003,
    "manager.center": 100002,
    "master.center": 100007,
    "dispatcher.demo": 200001,
    "director.pj2": 300001,
}


def upsert_user_by_username(
    session: Session,
    *,
    username: str,
    email: str,
    phone: str,
    first_name: str,
    last_name: str,
    role_code: str,
    tg_id: int,
    full_name: str | None = None,
    master_percentage: float | None = None,
) -> User:
    role = session.scalar(select(Role).where(Role.code == role_code))
    assert role is not None, f"role {role_code} missing — apply migration 0006 first"

    user = session.scalar(select(User).where(User.username == username))
    if user is None:
        user = User(
            username=username,
            email=email,
            phone=phone,
            password_hash=hash_password(DEFAULT_PASSWORD),
            first_name=first_name,
            last_name=last_name,
            status="active",
            role_id=role.id,
            tg_id=tg_id,
            full_name=full_name or f"{first_name} {last_name}",
            master_percentage=master_percentage,
        )
        session.add(user)
        session.flush()
        return user

    user.role_id = role.id
    user.tg_id = tg_id
    if full_name:
        user.full_name = full_name
    if master_percentage is not None:
        user.master_percentage = master_percentage
    return user


def set_existing_tg_id(session: Session, username: str, tg_id: int) -> None:
    user = session.scalar(select(User).where(User.username == username))
    if user is not None and user.tg_id is None:
        user.tg_id = tg_id


def get_or_create_city(session: Session, name: str, **kwargs) -> City:
    city = session.scalar(select(City).where(City.name == name))
    if city is None:
        city = City(name=name, **kwargs)
        session.add(city)
        session.flush()
    else:
        for k, v in kwargs.items():
            setattr(city, k, v)
    return city


def get_or_create_equipment_type(
    session: Session, name: str, *, master_pct: float = 60.0, company_pct: float = 40.0
) -> EquipmentType:
    et = session.scalar(select(EquipmentType).where(EquipmentType.name == name))
    if et is None:
        et = EquipmentType(name=name, master_pct=master_pct, company_pct=company_pct)
        session.add(et)
        session.flush()
    else:
        et.master_pct = master_pct
        et.company_pct = company_pct
    return et


def get_or_create_system_setting(
    session: Session, key: str, value: str, description: str | None = None
) -> SystemSettings:
    s = session.scalar(select(SystemSettings).where(SystemSettings.key == key))
    if s is None:
        s = SystemSettings(key=key, value=value, description=description)
        session.add(s)
        session.flush()
    else:
        s.value = value
        if description:
            s.description = description
    return s


def next_order_number(session: Session) -> int:
    max_num = session.scalar(select(Order.order_number).order_by(Order.order_number.desc()).limit(1))
    return (max_num or 0) + 1


def upsert_order(
    session: Session,
    *,
    order_number: int,
    city: City,
    status: str,
    equip_type: str,
    short_desc: str,
    client_name: str,
    client_phone: str,
    street: str,
    house: str,
    flat: str | None,
    time_from: str,
    time_to: str,
    order_date: datetime,
    created_by_tg: int,
    assigned_to_tg: int | None,
    source: str = "Звонок",
    sum_amount: float | None = None,
    paid_amount: float | None = None,
    sd_price: float | None = None,
    zpch_sum: float | None = None,
    comment: str | None = None,
) -> Order:
    o = session.scalar(select(Order).where(Order.order_number == order_number))
    if o is None:
        o = Order(order_number=order_number)
        session.add(o)
    o.city_id = city.id
    o.status = status
    o.equip_type = equip_type
    o.short_desc = short_desc
    o.client_name = client_name
    o.client_phone = client_phone
    o.street = street
    o.house = house
    o.flat = flat
    o.time_from = time_from
    o.time_to = time_to
    o.order_date = order_date
    o.created_by = created_by_tg
    o.assigned_to = assigned_to_tg
    o.source = source
    o.sum_amount = sum_amount
    o.paid_amount = paid_amount
    o.sd_price = sd_price
    o.zpch_sum = zpch_sum
    o.comment = comment
    if sum_amount is not None and paid_amount is not None:
        o.debt_amount = max(sum_amount - paid_amount, 0.0)
    session.flush()
    return o


def upsert_stat(
    session: Session,
    *,
    order_id: int,
    equip_type: str,
    sum_amount: float,
    master_tg: int,
    refused: bool = False,
    recorded_at: datetime | None = None,
) -> None:
    s = session.scalar(select(Stat).where(Stat.order_id == order_id))
    if s is None:
        s = Stat(order_id=order_id)
        session.add(s)
    s.equip_type = equip_type
    s.sum = sum_amount
    s.master_tg = master_tg
    s.refused = refused
    if recorded_at is not None:
        s.recorded_at = recorded_at


def main() -> None:
    session: Session = SessionLocal()
    try:
        # 1) Backfill tg_id on users created by seed_demo_data.py
        for username, tg_id in TG_IDS.items():
            set_existing_tg_id(session, username, tg_id)

        # 2) Set master percentage on master.center
        master_user = session.scalar(select(User).where(User.username == "master.center"))
        if master_user is not None:
            master_user.master_percentage = 60.0
            if master_user.full_name is None:
                master_user.full_name = "Сергей Мастеровой"

        # 3) Create PJ2-specific accounts
        dispatcher = upsert_user_by_username(
            session,
            username="dispatcher.demo",
            email="dispatcher.demo@promouters.local",
            phone="+79990000010",
            first_name="Анна",
            last_name="Диспетчер",
            role_code="dispatcher",
            tg_id=TG_IDS["dispatcher.demo"],
            full_name="Анна Диспетчер",
        )
        director_pj2 = upsert_user_by_username(
            session,
            username="director.pj2",
            email="director.pj2@promouters.local",
            phone="+79990000011",
            first_name="Виктор",
            last_name="Сервисов",
            role_code="director",
            tg_id=TG_IDS["director.pj2"],
            full_name="Виктор Сервисов",
        )

        # 4) Cities
        moscow = get_or_create_city(session, "Москва", cash_company_percentage=50.0, timezone="Europe/Moscow")
        spb = get_or_create_city(session, "Санкт-Петербург", cash_company_percentage=55.0, timezone="Europe/Moscow")
        kazan = get_or_create_city(session, "Казань", cash_company_percentage=50.0, timezone="Europe/Moscow")

        # 5) Equipment types
        get_or_create_equipment_type(session, "Бытовая техника", master_pct=60.0, company_pct=40.0)
        get_or_create_equipment_type(session, "ПК", master_pct=55.0, company_pct=45.0)
        get_or_create_equipment_type(session, "Телевизоры", master_pct=60.0, company_pct=40.0)
        get_or_create_equipment_type(session, "Другое", master_pct=50.0, company_pct=50.0)

        # 6) Commission config in system_settings
        get_or_create_system_setting(
            session,
            key=SETTINGS_KEY,
            value=json.dumps(DEFAULT_SETTINGS, ensure_ascii=False),
            description="Тарифная сетка комиссии мастера (категория → диапазоны сумм → %)",
        )

        # 7) Orders — fixed numbers so re-runs are idempotent
        master_tg = TG_IDS["master.center"]
        disp_tg = TG_IDS["dispatcher.demo"]
        dir_tg = TG_IDS["director.pj2"]

        upsert_order(
            session,
            order_number=10001,
            city=moscow,
            status="new",
            equip_type="Бытовая техника",
            short_desc="Не включается стиральная машина Bosch.",
            client_name="Иванов Иван",
            client_phone="+74950000001",
            street="Тверская",
            house="7",
            flat="12",
            time_from="10:00",
            time_to="12:00",
            order_date=NOW + timedelta(days=1),
            created_by_tg=disp_tg,
            assigned_to_tg=None,
            source="Звонок",
            sum_amount=None,
        )
        upsert_order(
            session,
            order_number=10002,
            city=moscow,
            status="accepted",
            equip_type="Телевизоры",
            short_desc="Тёмный экран на Samsung 55\".",
            client_name="Петров Пётр",
            client_phone="+74950000002",
            street="Манежная пл.",
            house="1",
            flat=None,
            time_from="14:00",
            time_to="16:00",
            order_date=NOW + timedelta(days=1),
            created_by_tg=disp_tg,
            assigned_to_tg=master_tg,
            source="Сайт",
        )
        upsert_order(
            session,
            order_number=10003,
            city=moscow,
            status="in_progress",
            equip_type="ПК",
            short_desc="Не загружается Windows на десктопе.",
            client_name="Сидоров Семён",
            client_phone="+74950000003",
            street="Пушкинская пл.",
            house="2",
            flat="44",
            time_from="11:00",
            time_to="13:00",
            order_date=NOW,
            created_by_tg=dir_tg,
            assigned_to_tg=master_tg,
            source="Постоянный клиент",
            sd_price=500.0,
        )
        order_done = upsert_order(
            session,
            order_number=10004,
            city=moscow,
            status="done",
            equip_type="Бытовая техника",
            short_desc="Замена ТЭНа стиральной машины.",
            client_name="Кафе Восход",
            client_phone="+74950003344",
            street="Большая Никитская",
            house="22",
            flat=None,
            time_from="09:00",
            time_to="11:00",
            order_date=NOW - timedelta(days=1),
            created_by_tg=disp_tg,
            assigned_to_tg=master_tg,
            source="Звонок",
            sum_amount=8500.0,
            paid_amount=8500.0,
            zpch_sum=2500.0,
            comment="Запчасти — ТЭН Indesit, гарантия 90 дней.",
        )
        upsert_order(
            session,
            order_number=10005,
            city=spb,
            status="to_sd",
            equip_type="Телевизоры",
            short_desc="Требуется снятие платы на СД (служба диагностики).",
            client_name="Студия Ясного",
            client_phone="+74950005566",
            street="Невский проспект",
            house="100",
            flat="5",
            time_from="15:00",
            time_to="17:00",
            order_date=NOW - timedelta(days=2),
            created_by_tg=disp_tg,
            assigned_to_tg=master_tg,
            source="Звонок",
            sd_price=1500.0,
            sum_amount=None,
        )
        upsert_order(
            session,
            order_number=10006,
            city=kazan,
            status="refused",
            equip_type="Другое",
            short_desc="Клиент отказался от ремонта (дорого).",
            client_name="ООО Ромашка",
            client_phone="+74950001122",
            street="Баумана",
            house="15",
            flat=None,
            time_from="13:00",
            time_to="15:00",
            order_date=NOW - timedelta(days=3),
            created_by_tg=dir_tg,
            assigned_to_tg=master_tg,
            source="Сайт",
        )

        session.flush()

        # 8) A couple of stats rows for the completed order
        if order_done.id is not None:
            upsert_stat(
                session,
                order_id=order_done.id,
                equip_type="Бытовая техника",
                sum_amount=8500.0,
                master_tg=master_tg,
                refused=False,
                recorded_at=NOW - timedelta(days=1, hours=2),
            )

        session.commit()

        print("PJ2 seed complete.")
        print("New accounts:")
        print(f"  dispatcher.demo / {DEFAULT_PASSWORD} / +79990000010  (роль: dispatcher)")
        print(f"  director.pj2 / {DEFAULT_PASSWORD} / +79990000011  (роль: director)")
        print()
        print(f"Cities: Москва (#{moscow.id}), Санкт-Петербург (#{spb.id}), Казань (#{kazan.id})")
        print("Equipment types: Бытовая техника / ПК / Телевизоры / Другое")
        print("Orders: 10001 (new), 10002 (accepted), 10003 (in_progress),")
        print("        10004 (done, 8500 RUB), 10005 (to_sd), 10006 (refused)")
        print(f"Master percentage on master.center set to 60% (tg_id={master_tg}).")
    finally:
        session.close()


if __name__ == "__main__":
    main()
