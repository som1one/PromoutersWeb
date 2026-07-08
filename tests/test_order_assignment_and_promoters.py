"""Regression tests for order master-assignment and ad_director promoter creation.

Covers the admin fixes:
* снятие мастера с заявки действительно сохраняется (Issue C);
* создание заявки с мастером помечается как «назначена» (Issue D);
* директор по рекламе может создавать промоутеров, но не редактировать/удалять (Issue A);
* дублирующийся VK ID при сохранении карточки даёт понятную ошибку, а не 500 (Issue B).
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from promouters.core.config import get_settings
from promouters.models.enums import RoleCode, UserStatus
from promouters.models.service_ops import Order
from promouters.models.users import User
from promouters.utils.jwt import create_jwt_token


class _SessionContext:
    def __init__(self, session):
        self._session = session

    def __enter__(self):
        return self._session

    def __exit__(self, exc_type, exc, tb):
        return False


@pytest.fixture(autouse=True)
def _reuse_test_session_for_template_helpers(monkeypatch, db_session):
    monkeypatch.setattr(
        "promouters.db.session.SessionLocal", lambda: _SessionContext(db_session)
    )


def _login(client, user: User) -> None:
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
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _make_order(db_session, *, number: int, assigned_to: int | None, status: str) -> Order:
    order = Order(
        order_number=number,
        assigned_to=assigned_to,
        status=status,
        street="Тестовая",
    )
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)
    return order


# --- Issue C: снятие мастера сохраняется -------------------------------------

def test_order_full_edit_can_unassign_master(client, db_session, seed_roles, seed_branch):
    owner = _make_user(db_session, seed_roles, seed_branch, role_code=RoleCode.OWNER, username="owner_c1")
    master = _make_user(db_session, seed_roles, seed_branch, role_code=RoleCode.MASTER, username="master_c1", tg_id=555001)
    order = _make_order(db_session, number=9001, assigned_to=master.tg_id, status="assigned")
    _login(client, owner)

    resp = client.post(
        f"/admin/orders/{order.id}",
        data={"assigned_to": "", "status": "new", "street": "Тестовая"},
        follow_redirects=False,
    )

    assert resp.status_code == 302
    db_session.refresh(order)
    assert order.assigned_to is None


def test_order_inline_update_can_unassign_master(client, db_session, seed_roles, seed_branch):
    owner = _make_user(db_session, seed_roles, seed_branch, role_code=RoleCode.OWNER, username="owner_c2")
    master = _make_user(db_session, seed_roles, seed_branch, role_code=RoleCode.MASTER, username="master_c2", tg_id=555002)
    order = _make_order(db_session, number=9002, assigned_to=master.tg_id, status="assigned")
    _login(client, owner)

    resp = client.post(
        f"/admin/orders/{order.id}/update",
        data={"assigned_to": "", "status": "new"},
        follow_redirects=False,
    )

    assert resp.status_code == 302
    db_session.refresh(order)
    assert order.assigned_to is None


# --- Issue D: создание с мастером = «назначена» ------------------------------

def test_order_create_with_master_is_marked_assigned(client, db_session, seed_roles, seed_branch):
    owner = _make_user(db_session, seed_roles, seed_branch, role_code=RoleCode.OWNER, username="owner_d1")
    master = _make_user(db_session, seed_roles, seed_branch, role_code=RoleCode.MASTER, username="master_d1", tg_id=555003)
    _login(client, owner)

    resp = client.post(
        "/admin/orders/create",
        data={"street": "Ленина", "assigned_to": str(master.tg_id)},
        follow_redirects=False,
    )

    assert resp.status_code == 302
    assert "assigned=1" in resp.headers["location"]
    order = db_session.scalar(select(Order).where(Order.street == "Ленина"))
    assert order is not None
    assert order.assigned_to == master.tg_id
    assert order.status == "assigned"


def test_order_create_without_master_is_new(client, db_session, seed_roles, seed_branch):
    owner = _make_user(db_session, seed_roles, seed_branch, role_code=RoleCode.OWNER, username="owner_d2")
    _login(client, owner)

    resp = client.post(
        "/admin/orders/create",
        data={"street": "Мира"},
        follow_redirects=False,
    )

    assert resp.status_code == 302
    assert "assigned=1" not in resp.headers["location"]
    order = db_session.scalar(select(Order).where(Order.street == "Мира"))
    assert order is not None
    assert order.assigned_to is None
    assert order.status == "new"


# --- Issue A: ad_director может создавать промоутеров, но не менять/удалять ----

def test_ad_director_can_create_promoter(client, db_session, seed_roles, seed_branch):
    ad = _make_user(db_session, seed_roles, seed_branch, role_code=RoleCode.AD_DIRECTOR, username="ad_a1")
    _login(client, ad)

    resp = client.post(
        "/admin/promoters/new",
        data={"first_name": "Иван", "last_name": "Промо", "tg_id": "770001"},
        follow_redirects=False,
    )

    assert resp.status_code == 302
    assert resp.headers["location"] == "/admin/promoters?created=1"
    promoter = db_session.scalar(select(User).where(User.tg_id == 770001))
    assert promoter is not None
    assert promoter.role.code == RoleCode.PROMOTER.value
    assert promoter.branch_id == seed_branch.id
    assert promoter.status == UserStatus.ACTIVE


def test_ad_director_cannot_delete_promoter(client, db_session, seed_roles, seed_branch):
    ad = _make_user(db_session, seed_roles, seed_branch, role_code=RoleCode.AD_DIRECTOR, username="ad_a2")
    promoter = _make_user(db_session, seed_roles, seed_branch, role_code=RoleCode.PROMOTER, username="promo_a2", tg_id=770002)
    _login(client, ad)

    resp = client.post(f"/admin/promoters/{promoter.id}/delete", follow_redirects=False)

    # Доступ запрещён рендерится страницей forbidden (в этом приложении она
    # отдаётся кодом 200), но удаление не выполняется.
    assert "Доступ запрещён" in resp.text
    assert resp.headers.get("location") != "/admin/promoters?deleted=1"
    db_session.refresh(promoter)
    assert promoter.status == UserStatus.ACTIVE


def test_ad_director_cannot_open_user_edit(client, db_session, seed_roles, seed_branch):
    ad = _make_user(db_session, seed_roles, seed_branch, role_code=RoleCode.AD_DIRECTOR, username="ad_a3")
    promoter = _make_user(db_session, seed_roles, seed_branch, role_code=RoleCode.PROMOTER, username="promo_a3", tg_id=770003)
    _login(client, ad)

    resp = client.get(f"/admin/users/{promoter.id}", follow_redirects=False)

    # Форма редактирования пользователя недоступна — показывается forbidden.
    assert "Доступ запрещён" in resp.text
    assert "Telegram ID (VK ID)" not in resp.text


# --- Issue B: дублирующийся VK ID = понятная ошибка, не 500 -------------------

def test_user_update_duplicate_vk_id_is_friendly(client, db_session, seed_roles, seed_branch):
    owner = _make_user(db_session, seed_roles, seed_branch, role_code=RoleCode.OWNER, username="owner_b1")
    m1 = _make_user(db_session, seed_roles, seed_branch, role_code=RoleCode.MASTER, username="master_b1", tg_id=880001)
    m2 = _make_user(db_session, seed_roles, seed_branch, role_code=RoleCode.MASTER, username="master_b2", tg_id=880002)
    _login(client, owner)

    resp = client.post(
        f"/admin/users/{m2.id}",
        data={
            "first_name": "Мастер",
            "last_name": "Второй",
            "phone": m2.phone,
            "email": m2.email,
            "role_code": RoleCode.MASTER.value,
            "tg_id": "880001",  # already used by m1
            "status_code": "active",
            "branch_id": str(seed_branch.id),
        },
        follow_redirects=False,
    )

    assert resp.status_code == 200  # re-render with error, not 302 and not 500
    assert "VK ID" in resp.text
    db_session.refresh(m2)
    assert m2.tg_id == 880002  # unchanged
