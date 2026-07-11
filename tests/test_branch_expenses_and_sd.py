"""Тесты для «Расходов филиала» и починенной страницы СД.

Покрывают: создание расхода директором по рекламе (с чеком / без чека+комментарий),
правило «чек ИЛИ комментарий», права (branch_manager — просмотр, ad_director — без
ред./удаления, owner — полный доступ), филиальную видимость и вывод SD-заявок.
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import select

from promouters.core.config import get_settings
from promouters.models.enums import RoleCode, UserStatus
from promouters.models.finance import BranchExpense
from promouters.models.service_ops import Order
from promouters.models.users import Branch, User
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


def _make_user(db_session, seed_roles, branch, *, role_code: RoleCode, username: str, tg_id=None) -> User:
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
        branch_id=None if role_code == RoleCode.OWNER else (branch.id if branch else None),
        tg_id=tg_id,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _make_expense(db_session, *, branch, creator, topic="Аренда", amount="1000.00", no_receipt=True, comment="ком") -> BranchExpense:
    expense = BranchExpense(
        branch_id=branch.id,
        created_by_id=creator.id,
        topic=topic,
        amount=Decimal(amount),
        currency="RUB",
        no_receipt=no_receipt,
        comment=comment,
    )
    db_session.add(expense)
    db_session.commit()
    db_session.refresh(expense)
    return expense


def _make_branch(db_session, *, name, code) -> Branch:
    branch = Branch(name=name, code=code, city="Город", is_active=True)
    db_session.add(branch)
    db_session.commit()
    db_session.refresh(branch)
    return branch


# --- Создание ---------------------------------------------------------------

def test_ad_director_can_create_expense_with_receipt(client, db_session, seed_roles, seed_branch, monkeypatch, tmp_path):
    monkeypatch.setattr(get_settings(), "media_root", str(tmp_path))
    ad = _make_user(db_session, seed_roles, seed_branch, role_code=RoleCode.AD_DIRECTOR, username="ad_e1")
    _login(client, ad)

    resp = client.post(
        "/admin/branch-expenses/new",
        data={"topic": "Листовки", "amount": "1500.50"},
        files={"receipt": ("chek.png", b"fakebytes", "image/png")},
        follow_redirects=False,
    )

    assert resp.status_code == 302
    assert resp.headers["location"] == "/admin/branch-expenses?created=1"
    expense = db_session.scalar(select(BranchExpense).where(BranchExpense.topic == "Листовки"))
    assert expense is not None
    assert expense.branch_id == seed_branch.id
    assert expense.created_by_id == ad.id
    assert expense.amount == Decimal("1500.50")
    assert expense.receipt_path and expense.receipt_path.startswith("expense_receipts/")
    assert expense.no_receipt is False


def test_create_no_receipt_requires_comment(client, db_session, seed_roles, seed_branch):
    ad = _make_user(db_session, seed_roles, seed_branch, role_code=RoleCode.AD_DIRECTOR, username="ad_e2")
    _login(client, ad)

    resp = client.post(
        "/admin/branch-expenses/new",
        data={"topic": "Без чека", "amount": "300", "no_receipt": "on"},
        follow_redirects=False,
    )

    assert resp.status_code == 200  # перерисовка с ошибкой, не редирект
    assert "чек" in resp.text.lower()
    assert db_session.scalar(select(BranchExpense).where(BranchExpense.topic == "Без чека")) is None


def test_create_no_receipt_with_comment_ok(client, db_session, seed_roles, seed_branch):
    ad = _make_user(db_session, seed_roles, seed_branch, role_code=RoleCode.AD_DIRECTOR, username="ad_e3")
    _login(client, ad)

    resp = client.post(
        "/admin/branch-expenses/new",
        data={"topic": "Такси", "amount": "450", "no_receipt": "on", "comment": "поездка на объект"},
        follow_redirects=False,
    )

    assert resp.status_code == 302
    expense = db_session.scalar(select(BranchExpense).where(BranchExpense.topic == "Такси"))
    assert expense is not None
    assert expense.no_receipt is True
    assert expense.comment == "поездка на объект"
    assert expense.receipt_path is None


# --- Права ------------------------------------------------------------------

def test_branch_manager_is_view_only(client, db_session, seed_roles, seed_branch):
    bm = _make_user(db_session, seed_roles, seed_branch, role_code=RoleCode.BRANCH_MANAGER, username="bm_e1")
    _login(client, bm)

    # форма создания недоступна
    form_resp = client.get("/admin/branch-expenses/new", follow_redirects=False)
    assert "Доступ запрещён" in form_resp.text

    # даже с валидными данными расход не создаётся
    client.post(
        "/admin/branch-expenses/new",
        data={"topic": "Попытка", "amount": "100", "no_receipt": "on", "comment": "x"},
        follow_redirects=False,
    )
    assert db_session.scalar(select(BranchExpense).where(BranchExpense.topic == "Попытка")) is None

    # но список ему доступен
    list_resp = client.get("/admin/branch-expenses")
    assert list_resp.status_code == 200
    assert "Расходы филиала" in list_resp.text


def test_branch_manager_sees_only_own_branch(client, db_session, seed_roles, seed_branch):
    other = _make_branch(db_session, name="Другой филиал", code="OTH")
    owner = _make_user(db_session, seed_roles, seed_branch, role_code=RoleCode.OWNER, username="owner_scope")
    bm = _make_user(db_session, seed_roles, seed_branch, role_code=RoleCode.BRANCH_MANAGER, username="bm_scope")
    _make_expense(db_session, branch=seed_branch, creator=owner, topic="Мой-филиал-расход")
    _make_expense(db_session, branch=other, creator=owner, topic="Чужой-филиал-расход")
    _login(client, bm)

    resp = client.get("/admin/branch-expenses")
    assert resp.status_code == 200
    assert "Мой-филиал-расход" in resp.text
    assert "Чужой-филиал-расход" not in resp.text


def test_ad_director_cannot_edit_or_delete(client, db_session, seed_roles, seed_branch):
    ad = _make_user(db_session, seed_roles, seed_branch, role_code=RoleCode.AD_DIRECTOR, username="ad_e4")
    owner = _make_user(db_session, seed_roles, seed_branch, role_code=RoleCode.OWNER, username="owner_e4")
    expense = _make_expense(db_session, branch=seed_branch, creator=owner, topic="Неприкасаемый")
    _login(client, ad)

    edit_resp = client.get(f"/admin/branch-expenses/{expense.id}/edit", follow_redirects=False)
    assert "Доступ запрещён" in edit_resp.text

    del_resp = client.post(f"/admin/branch-expenses/{expense.id}/delete", follow_redirects=False)
    assert "Доступ запрещён" in del_resp.text
    assert del_resp.headers.get("location") != "/admin/branch-expenses?deleted=1"
    assert db_session.get(BranchExpense, expense.id) is not None


def test_owner_can_edit_and_delete(client, db_session, seed_roles, seed_branch):
    owner = _make_user(db_session, seed_roles, seed_branch, role_code=RoleCode.OWNER, username="owner_e5")
    expense = _make_expense(db_session, branch=seed_branch, creator=owner, topic="Старое", amount="100.00")
    _login(client, owner)

    edit_resp = client.post(
        f"/admin/branch-expenses/{expense.id}/edit",
        data={"topic": "Новое", "amount": "250", "no_receipt": "on", "comment": "правка"},
        follow_redirects=False,
    )
    assert edit_resp.status_code == 302
    assert edit_resp.headers["location"] == "/admin/branch-expenses?updated=1"
    db_session.expire_all()
    updated = db_session.get(BranchExpense, expense.id)
    assert updated.topic == "Новое"
    assert updated.amount == Decimal("250.00")

    del_resp = client.post(f"/admin/branch-expenses/{expense.id}/delete", follow_redirects=False)
    assert del_resp.status_code == 302
    assert del_resp.headers["location"] == "/admin/branch-expenses?deleted=1"
    assert db_session.get(BranchExpense, expense.id) is None


def test_owner_must_pick_branch(client, db_session, seed_roles, seed_branch):
    owner = _make_user(db_session, seed_roles, seed_branch, role_code=RoleCode.OWNER, username="owner_e6")
    _login(client, owner)

    missing = client.post(
        "/admin/branch-expenses/new",
        data={"topic": "Без филиала", "amount": "100", "no_receipt": "on", "comment": "x"},
        follow_redirects=False,
    )
    assert missing.status_code == 200
    assert "филиал" in missing.text.lower()
    assert db_session.scalar(select(BranchExpense).where(BranchExpense.topic == "Без филиала")) is None

    ok = client.post(
        "/admin/branch-expenses/new",
        data={"topic": "С филиалом", "amount": "100", "no_receipt": "on", "comment": "x", "branch_id": str(seed_branch.id)},
        follow_redirects=False,
    )
    assert ok.status_code == 302
    created = db_session.scalar(select(BranchExpense).where(BranchExpense.topic == "С филиалом"))
    assert created is not None
    assert created.branch_id == seed_branch.id


# --- SD-страница ------------------------------------------------------------

def test_sd_page_lists_orders_grouped_by_master(client, db_session, seed_roles, seed_branch):
    owner = _make_user(db_session, seed_roles, seed_branch, role_code=RoleCode.OWNER, username="owner_sd")
    master = _make_user(db_session, seed_roles, seed_branch, role_code=RoleCode.MASTER, username="sidelnikov", tg_id=444001)
    for i, num in enumerate((7001, 7002, 7003)):
        db_session.add(Order(
            order_number=num,
            assigned_to=master.tg_id,
            status="to_sd",
            street=f"Улица {i}",
            sd_price=1000 + num,
            zpch_sum=100,
        ))
    db_session.commit()
    _login(client, owner)

    resp = client.get("/admin/sd")

    assert resp.status_code == 200
    assert "Нет данных" not in resp.text
    assert "sidelnikov" in resp.text  # имя мастера (first_name)
    for num in ("7001", "7002", "7003"):
        assert num in resp.text
