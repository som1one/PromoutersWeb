"""Unit tests for RouteCommandHandler.handle_start_shift."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from promouters.integrations.vk_bot.handlers.routes import RouteCommandHandler
from promouters.models.enums import (
    PromoterSessionStatus,
    RoleCode,
    RouteStatus,
    UserStatus,
)
from promouters.models.routing import PromoterSession, Route
from promouters.models.users import Branch, Role, User


@pytest.fixture()
def branch(db_session: Session) -> Branch:
    branch = Branch(name="Тест филиал", code="TST", city="Москва", is_active=True)
    db_session.add(branch)
    db_session.commit()
    db_session.refresh(branch)
    return branch


@pytest.fixture()
def promoter_role(db_session: Session) -> Role:
    role = Role(code=RoleCode.PROMOTER.value, name="Промоутер", is_system=True)
    db_session.add(role)
    db_session.commit()
    db_session.refresh(role)
    return role


@pytest.fixture()
def owner_role(db_session: Session) -> Role:
    role = Role(code=RoleCode.OWNER.value, name="Собственник", is_system=True)
    db_session.add(role)
    db_session.commit()
    db_session.refresh(role)
    return role


@pytest.fixture()
def promoter(db_session: Session, branch: Branch, promoter_role: Role) -> User:
    user = User(
        username="promoter_test",
        email="promoter@test.local",
        phone="+79990001111",
        password_hash="hashed",
        first_name="Иван",
        last_name="Петров",
        status=UserStatus.ACTIVE,
        is_superuser=False,
        role_id=promoter_role.id,
        branch_id=branch.id,
        vk_id="12345",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def owner(db_session: Session, branch: Branch, owner_role: Role) -> User:
    user = User(
        username="owner_test",
        email="owner@test.local",
        phone="+79990002222",
        password_hash="hashed",
        first_name="Админ",
        last_name="Тестов",
        status=UserStatus.ACTIVE,
        is_superuser=True,
        role_id=owner_role.id,
        branch_id=branch.id,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def assigned_route(db_session: Session, branch: Branch, promoter: User, owner: User) -> Route:
    route = Route(
        title="Маршрут центр",
        work_date=date.today(),
        status=RouteStatus.ASSIGNED,
        branch_id=branch.id,
        promoter_id=promoter.id,
        created_by_id=owner.id,
    )
    db_session.add(route)
    db_session.commit()
    db_session.refresh(route)
    return route


@pytest.fixture()
def handler(db_session: Session) -> RouteCommandHandler:
    return RouteCommandHandler(db=db_session)


class TestHandleStartShift:
    """Tests for handle_start_shift."""

    def test_successful_start_without_geo(
        self, handler: RouteCommandHandler, db_session: Session, assigned_route: Route, promoter: User
    ):
        """Successfully starts a shift and returns confirmation with route title and time."""
        result = handler.handle_start_shift(user_id=12345, geo=None)

        assert "Смена начата" in result
        assert "Маршрут центр" in result

        # Verify session was created
        session = db_session.scalar(
            db_session.query(PromoterSession)
            .filter(PromoterSession.promoter_id == promoter.id)
            .statement
        )
        assert session is not None
        assert session.status == PromoterSessionStatus.ACTIVE
        assert session.started_at is not None
        assert session.started_latitude is None
        assert session.started_longitude is None

        # Verify route status changed
        db_session.refresh(assigned_route)
        assert assigned_route.status == RouteStatus.IN_PROGRESS

    def test_successful_start_with_geo(
        self, handler: RouteCommandHandler, db_session: Session, assigned_route: Route, promoter: User
    ):
        """Records geo coordinates when provided."""
        geo = {"latitude": 55.7558, "longitude": 37.6173}
        result = handler.handle_start_shift(user_id=12345, geo=geo)

        assert "Смена начата" in result

        # Verify geo was recorded
        session = db_session.scalar(
            db_session.query(PromoterSession)
            .filter(PromoterSession.promoter_id == promoter.id)
            .statement
        )
        assert session is not None
        assert float(session.started_latitude) == pytest.approx(55.7558, rel=1e-4)
        assert float(session.started_longitude) == pytest.approx(37.6173, rel=1e-4)

    def test_no_route_today(self, handler: RouteCommandHandler, promoter: User):
        """Returns error when no assigned route exists for today."""
        # promoter has no routes
        result = handler.handle_start_shift(user_id=12345, geo=None)
        assert result == "На сегодня нет назначенных маршрутов."

    def test_already_active_session(
        self, handler: RouteCommandHandler, db_session: Session, assigned_route: Route, promoter: User
    ):
        """Returns error when promoter already has an active session."""
        # Create an existing active session
        existing = PromoterSession(
            route_id=assigned_route.id,
            promoter_id=promoter.id,
            started_at=datetime.now(UTC),
            status=PromoterSessionStatus.ACTIVE,
        )
        db_session.add(existing)
        db_session.commit()

        result = handler.handle_start_shift(user_id=12345, geo=None)
        assert result == "У вас уже есть активная смена. Завершите её перед началом новой."

    def test_unknown_vk_user(self, handler: RouteCommandHandler):
        """Returns error for unrecognized VK user."""
        result = handler.handle_start_shift(user_id=99999, geo=None)
        assert result == "Пользователь не найден в системе."

    def test_route_for_different_date_not_found(
        self, handler: RouteCommandHandler, db_session: Session, branch: Branch, promoter: User, owner: User
    ):
        """Does not pick up routes with different work_date."""
        # Route for tomorrow
        tomorrow_route = Route(
            title="Маршрут завтра",
            work_date=date.today() + timedelta(days=1),
            status=RouteStatus.ASSIGNED,
            branch_id=branch.id,
            promoter_id=promoter.id,
            created_by_id=owner.id,
        )
        db_session.add(tomorrow_route)
        db_session.commit()

        result = handler.handle_start_shift(user_id=12345, geo=None)
        assert result == "На сегодня нет назначенных маршрутов."

    def test_draft_route_not_found(
        self, handler: RouteCommandHandler, db_session: Session, branch: Branch, promoter: User, owner: User
    ):
        """Does not pick up routes with status draft."""
        draft_route = Route(
            title="Черновик маршрут",
            work_date=date.today(),
            status=RouteStatus.DRAFT,
            branch_id=branch.id,
            promoter_id=promoter.id,
            created_by_id=owner.id,
        )
        db_session.add(draft_route)
        db_session.commit()

        result = handler.handle_start_shift(user_id=12345, geo=None)
        assert result == "На сегодня нет назначенных маршрутов."
