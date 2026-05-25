"""Общие фикстуры для тестов backend СУУПР.

Поднимают изолированную SQLite БД на каждый тест и подменяют get_db,
чтобы не требовать запущенный PostgreSQL.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Iterator
from pathlib import Path

# pytest подхватит src как pythonpath из pyproject.toml, но повторим это явно
SRC_PATH = Path(__file__).resolve().parents[1] / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

# Тестовые настройки до импорта приложения, чтобы не дёргать реальный Postgres
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("AUTH_SMS_ENABLED", "false")
os.environ.setdefault("PHOTO_REPORT_REMINDERS_ENABLED", "false")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from promouters.db.base import Base
from promouters.db.session import get_db
from promouters.main import app
from promouters.models.enums import RoleCode, UserStatus
from promouters.models.users import Branch, Role, User
from promouters.utils.passwords import hash_password


# Сообщаем SQLAlchemy, как рендерить JSONB на SQLite
@compiles(JSONB, "sqlite")  # type: ignore[misc]
def _compile_jsonb_for_sqlite(element, compiler, **kw):  # pragma: no cover - служебное
    return "JSON"


@pytest.fixture()
def engine():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture()
def db_session(engine) -> Iterator[Session]:
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def seed_roles(db_session: Session) -> dict[str, Role]:
    roles: dict[str, Role] = {}
    role_definitions = [
        (RoleCode.OWNER, "Собственник"),
        (RoleCode.BRANCH_MANAGER, "Руководитель филиала"),
        (RoleCode.AD_DIRECTOR, "Директор по рекламе"),
        (RoleCode.DISPATCHER, "Диспетчер"),
        (RoleCode.DIRECTOR, "Директор"),
        (RoleCode.MASTER, "Мастер"),
        (RoleCode.PROMOTER, "Промоутер"),
        (RoleCode.USER, "Пользователь"),
    ]
    for code, name in role_definitions:
        role = Role(code=code.value, name=name, is_system=True)
        db_session.add(role)
        roles[code.value] = role
    db_session.commit()
    for role in roles.values():
        db_session.refresh(role)
    return roles


@pytest.fixture()
def seed_branch(db_session: Session) -> Branch:
    branch = Branch(name="Тестовый филиал", code="TEST", city="Москва", is_active=True)
    db_session.add(branch)
    db_session.commit()
    db_session.refresh(branch)
    return branch


@pytest.fixture()
def client(db_session: Session) -> Iterator[TestClient]:
    def _override_get_db() -> Iterator[Session]:
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture()
def user_factory(db_session: Session, seed_roles, seed_branch):
    """Создаёт пользователя нужной роли и возвращает (user, password)."""

    counter = {"value": 0}

    def _create(
        role_code: RoleCode,
        *,
        branch: Branch | None = None,
        username: str | None = None,
        phone: str | None = None,
    ) -> tuple[User, str]:
        counter["value"] += 1
        idx = counter["value"]
        target_branch = branch if branch is not None else seed_branch
        user_branch_id = None if role_code == RoleCode.OWNER and branch is None else target_branch.id
        password = "test-password-12345"
        user = User(
            username=username or f"{role_code.value}_{idx}",
            email=f"{role_code.value}{idx}@test.local",
            phone=phone or f"+7999000{idx:04d}",
            password_hash=hash_password(password),
            first_name=role_code.value.title(),
            last_name=f"User {idx}",
            middle_name=None,
            status=UserStatus.ACTIVE,
            is_superuser=role_code == RoleCode.OWNER,
            role_id=seed_roles[role_code.value].id,
            branch_id=user_branch_id,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user, password

    return _create


@pytest.fixture()
def login_helper(client: TestClient):
    """Возвращает функцию для логина и получения access_token."""

    def _login(phone: str, password: str) -> str:
        response = client.post(
            "/api/v1/auth/login",
            json={"phone": phone, "password": password},
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["access_token"], data
        return data["access_token"]

    return _login


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
