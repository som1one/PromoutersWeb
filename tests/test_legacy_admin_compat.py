from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from promouters.core.config import get_settings
from promouters.models.enums import RoleCode, UserStatus
from promouters.models.service_ops import City, Order, Stat, SystemSettings
from promouters.models.users import User
from promouters.utils.jwt import create_jwt_token, create_refresh_jwt_token


class _SessionContext:
    def __init__(self, session):
        self._session = session

    def __enter__(self):
        return self._session

    def __exit__(self, exc_type, exc, tb):
        return False


@pytest.fixture(autouse=True)
def _reuse_test_session_for_template_helpers(monkeypatch, db_session):
    monkeypatch.setattr("promouters.db.session.SessionLocal", lambda: _SessionContext(db_session))


def _login_as_web_user(client, user: User) -> None:
    settings = get_settings()
    client.cookies.set(
        "access_token",
        create_jwt_token(
            user_id=str(user.id),
            secret=settings.jwt_secret,
            expiration_time=settings.jwt_expiration_time,
            algorithm=settings.jwt_algorithm,
        ),
    )
    client.cookies.set(
        "refresh_token",
        create_refresh_jwt_token(
            user_id=str(user.id),
            refresh_secret=settings.jwt_refresh_secret,
            refresh_expiration_time=settings.jwt_refresh_expiration_time,
            refresh_algorithm=settings.jwt_refresh_algorithm,
        ),
    )


def _make_user(
    db_session,
    seed_roles,
    seed_branch,
    *,
    role_code: RoleCode,
    username: str,
    tg_id: int | None = None,
) -> User:
    user = User(
        username=username,
        email=f"{username}@test.local",
        phone=f"+7{abs(hash(username)) % 10_000_000_000:010d}",
        password_hash="test-hash",
        first_name=username,
        last_name="user",
        middle_name=None,
        status=UserStatus.ACTIVE,
        is_superuser=role_code == RoleCode.OWNER,
        role_id=seed_roles[role_code.value].id,
        branch_id=None if role_code == RoleCode.OWNER else seed_branch.id,
        tg_id=tg_id,
        full_name=username.replace("_", " ").title(),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _make_city(db_session, name: str = "Москва") -> City:
    city = City(name=name, cash_company_percentage=50.0, timezone="Europe/Moscow")
    db_session.add(city)
    db_session.commit()
    db_session.refresh(city)
    return city


def _make_order(
    db_session,
    *,
    city_id: int,
    assigned_to: int | None = None,
    status: str = "done_pending_sum",
    created_at: datetime | None = None,
) -> Order:
    order = Order(
        order_number=101,
        city_id=city_id,
        street="Ленина",
        house="10",
        flat="5",
        order_date=datetime.now(),
        equip_type="appliance",
        short_desc="Проверка",
        source="site",
        status=status,
        assigned_to=assigned_to,
        client_phone="+79990001122",
        client_name="Тест Клиент",
        sum_amount=5000.0,
        sd_price=1000.0,
        zpch_sum=500.0,
        created_at=created_at or datetime.now(),
    )
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)
    return order


def test_order_detail_and_search_work(client, db_session, seed_roles, seed_branch):
    owner = _make_user(db_session, seed_roles, seed_branch, role_code=RoleCode.OWNER, username="owner_orders")
    city = _make_city(db_session)
    order = _make_order(db_session, city_id=city.id)
    _login_as_web_user(client, owner)

    detail = client.get(f"/admin/orders/{order.id}")
    assert detail.status_code == 200
    assert "Тест Клиент" in detail.text

    search = client.get("/admin/orders/search", params={"phone": "1122"})
    assert search.status_code == 200
    assert f"/admin/orders/{order.id}" in search.text


def test_company_form_saves_profile(client, db_session, seed_roles, seed_branch):
    owner = _make_user(db_session, seed_roles, seed_branch, role_code=RoleCode.OWNER, username="owner_company")
    _login_as_web_user(client, owner)

    response = client.post(
        "/admin/company/form",
        data={
            "website": "example.com",
            "social_networks": "vk.com/test, instagram.com/test",
            "categories": ["Автоуслуги", "Красота"],
            "description": "Описание компании",
            "prepayment_available": "on",
            "phone_number": "+79990000000",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    row = db_session.scalar(select(SystemSettings).where(SystemSettings.key == "company_profile"))
    assert row is not None
    assert "example.com" in (row.value or "")


def test_legacy_export_routes_return_files(client, db_session, seed_roles, seed_branch):
    owner = _make_user(db_session, seed_roles, seed_branch, role_code=RoleCode.OWNER, username="owner_export")
    master = _make_user(
        db_session,
        seed_roles,
        seed_branch,
        role_code=RoleCode.MASTER,
        username="master_export",
        tg_id=123456,
    )
    city = _make_city(db_session)
    _make_order(db_session, city_id=city.id, assigned_to=master.tg_id, created_at=datetime.now() - timedelta(days=1))
    _login_as_web_user(client, owner)

    masters_export = client.get("/admin/export/masters", params={"format": "csv"})
    assert masters_export.status_code == 200
    assert "text/csv" in masters_export.headers["content-type"]

    orders_export = client.get("/admin/export/orders", params={"format": "csv", "days": 30})
    assert orders_export.status_code == 200
    assert "text/csv" in orders_export.headers["content-type"]


def test_cash_accept_and_extended_stats(client, db_session, seed_roles, seed_branch):
    owner = _make_user(db_session, seed_roles, seed_branch, role_code=RoleCode.OWNER, username="owner_cash")
    master = _make_user(
        db_session,
        seed_roles,
        seed_branch,
        role_code=RoleCode.MASTER,
        username="master_cash",
        tg_id=222333,
    )
    city = _make_city(db_session)
    pending_order = _make_order(db_session, city_id=city.id, assigned_to=master.tg_id, status="done_pending_sum")
    _login_as_web_user(client, owner)

    accept = client.post(f"/admin/cash/accept-order/{pending_order.id}", follow_redirects=False)
    assert accept.status_code == 302
    db_session.refresh(pending_order)
    assert pending_order.status == "completed"
    assert db_session.scalar(select(Stat).where(Stat.order_id == pending_order.id)) is not None

    stats = client.get("/admin/api/stats/extended")
    assert stats.status_code == 200
    body = stats.json()
    assert "equipment" in body
    assert "conversion" in body


def test_legacy_redirects_resolve_current_pages(client, db_session, seed_roles, seed_branch):
    owner = _make_user(db_session, seed_roles, seed_branch, role_code=RoleCode.OWNER, username="owner_legacy")
    master = _make_user(
        db_session,
        seed_roles,
        seed_branch,
        role_code=RoleCode.MASTER,
        username="master_legacy",
        tg_id=999111,
    )
    city = _make_city(db_session)
    order = _make_order(db_session, city_id=city.id, assigned_to=master.tg_id)
    _login_as_web_user(client, owner)

    assert client.get("/admin/create-order", follow_redirects=False).headers["location"] == "/admin/orders/create"
    assert client.get(f"/admin/order/{order.id}", follow_redirects=False).headers["location"] == f"/admin/orders/{order.id}"
    assert client.get(f"/admin/master/{master.tg_id}", follow_redirects=False).headers["location"] == f"/admin/masters/{master.id}"
