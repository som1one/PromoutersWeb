from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import select

from promouters.core.config import get_settings
from promouters.models.enums import ExpensePlanStatus, RoleCode, UserStatus
from promouters.models.finance import ExpensePlan
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


def _make_user(db_session, seed_roles, seed_branch, *, role_code: RoleCode, username: str) -> User:
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
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_admin_login_clears_stale_auth_cookies(client) -> None:
    client.cookies.set("access_token", "stale-token")
    client.cookies.set("refresh_token", "stale-refresh")

    response = client.get("/admin/login")

    assert response.status_code == 200
    set_cookie_headers = response.headers.get_list("set-cookie")
    assert any("access_token=" in header and "Max-Age=0" in header for header in set_cookie_headers)
    assert any("refresh_token=" in header and "Max-Age=0" in header for header in set_cookie_headers)


def test_user_delete_archives_and_hides_from_active_list(
    client, db_session, seed_roles, seed_branch
) -> None:
    owner = _make_user(db_session, seed_roles, seed_branch, role_code=RoleCode.OWNER, username="owner_web")
    target = _make_user(db_session, seed_roles, seed_branch, role_code=RoleCode.BRANCH_MANAGER, username="delete_me_user")
    _login_as_web_user(client, owner)

    response = client.post(f"/admin/users/{target.id}/delete", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "/admin/users?deleted=1"

    db_session.refresh(target)
    assert target.status == UserStatus.INACTIVE
    assert target.username.startswith("archived_")
    assert target.phone is None

    active_list = client.get("/admin/users")
    assert active_list.status_code == 200
    assert "delete_me_user" not in active_list.text

    inactive_list = client.get("/admin/users?status_code=inactive")
    assert inactive_list.status_code == 200
    assert target.username in inactive_list.text


def test_promoter_delete_archives_and_hides_from_promoters_list(
    client, db_session, seed_roles, seed_branch
) -> None:
    owner = _make_user(db_session, seed_roles, seed_branch, role_code=RoleCode.OWNER, username="owner_promoters")
    promoter = _make_user(db_session, seed_roles, seed_branch, role_code=RoleCode.PROMOTER, username="delete_me_promoter")
    _login_as_web_user(client, owner)

    response = client.post(f"/admin/promoters/{promoter.id}/delete", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "/admin/promoters?deleted=1"

    db_session.refresh(promoter)
    assert promoter.status == UserStatus.INACTIVE
    assert promoter.username.startswith("archived_")

    promoters_list = client.get("/admin/promoters")
    assert promoters_list.status_code == 200
    assert "delete_me_promoter" not in promoters_list.text


def test_expense_plan_create_from_google_sheet_rows(
    client, db_session, seed_roles, seed_branch
) -> None:
    manager = _make_user(db_session, seed_roles, seed_branch, role_code=RoleCode.BRANCH_MANAGER, username="sheet_manager")
    _login_as_web_user(client, manager)

    today = date.today()
    response = client.post(
        "/admin/expense-plans/create",
        data={
            "title": "sheet-import-plan",
            "branch_id": str(seed_branch.id),
            "period_start": today.isoformat(),
            "period_end": (today + timedelta(days=7)).isoformat(),
            "comment": "draft from sheet",
            "sheet_rows": "Promo shift\tPromo\t2\t1500\tMorning\nLeaflets\tMaterials\t300\t2.5\tPrint",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    plan = db_session.scalar(select(ExpensePlan).where(ExpensePlan.title == "sheet-import-plan"))
    assert plan is not None
    assert len(plan.items) == 2
    assert float(plan.total_amount) == 3750.0
    assert plan.status == ExpensePlanStatus.DRAFT


def test_expense_plan_submit_requires_items_for_draft(
    client, db_session, seed_roles, seed_branch
) -> None:
    manager = _make_user(db_session, seed_roles, seed_branch, role_code=RoleCode.BRANCH_MANAGER, username="empty_plan_manager")
    _login_as_web_user(client, manager)

    today = date.today()
    create_response = client.post(
        "/admin/expense-plans/create",
        data={
            "title": "empty-draft-plan",
            "branch_id": str(seed_branch.id),
            "period_start": today.isoformat(),
            "period_end": today.isoformat(),
            "comment": "empty draft",
            "sheet_rows": "",
        },
        follow_redirects=False,
    )
    assert create_response.status_code == 302

    plan = db_session.scalar(select(ExpensePlan).where(ExpensePlan.title == "empty-draft-plan"))
    assert plan is not None
    assert len(plan.items) == 0

    submit_response = client.post(f"/admin/expense-plans/{plan.id}/submit")

    assert submit_response.status_code == 200
    db_session.refresh(plan)
    assert plan.status == ExpensePlanStatus.DRAFT
