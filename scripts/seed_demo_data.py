from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from promouters.db.session import SessionLocal
from promouters.models.enums import (
    ExpenseApprovalDecision,
    ExpensePlanStatus,
    GeoPingSource,
    MasterRequestStatus,
    NotificationChannel,
    NotificationStatus,
    PhotoReportStatus,
    PayoutRateType,
    PayoutStatus,
    PromoterSessionStatus,
    RoleCode,
    RoutePointType,
    RouteStatus,
    UserStatus,
)
from promouters.models.finance import ExpenseApproval, ExpensePlan, ExpensePlanItem, Payout, PayoutRate
from promouters.models.operations import (
    AuditLog,
    MasterRequest,
    MasterRequestComment,
    MasterRequestStatusLog,
    Notification,
)
from promouters.models.routing import GeoPing, PhotoReport, PromoterSession, Route, RoutePoint
from promouters.models.users import Branch, Role, User
from promouters.utils.passwords import hash_password

DEFAULT_PASSWORD = "demo12345"


def get_or_create_role(session: Session, code: RoleCode, name: str, description: str) -> Role:
    role = session.scalar(select(Role).where(Role.code == code.value))
    if role is None:
        role = Role(code=code.value, name=name, description=description, is_system=True)
        session.add(role)
        session.flush()
    else:
        role.name = name
        role.description = description
        role.is_system = True
    return role


def get_or_create_branch(
    session: Session,
    *,
    code: str,
    name: str,
    city: str,
    address: str,
) -> Branch:
    branch = session.scalar(select(Branch).where(Branch.code == code))
    if branch is None:
        branch = Branch(code=code, name=name, city=city, address=address, is_active=True)
        session.add(branch)
        session.flush()
    else:
        branch.name = name
        branch.city = city
        branch.address = address
        branch.is_active = True
    return branch


def get_or_create_user(
    session: Session,
    *,
    username: str,
    email: str,
    phone: str,
    first_name: str,
    last_name: str,
    role: Role,
    branch: Branch | None,
    password: str = DEFAULT_PASSWORD,
    is_superuser: bool = False,
) -> User:
    user = session.scalar(select(User).where(User.username == username))
    if user is None and phone:
        user = session.scalar(select(User).where(User.phone == phone))
    if user is None:
        user = session.scalar(select(User).where(User.email == email))

    if user is None:
        user = User(
            username=username,
            email=email,
            phone=phone,
            password_hash=hash_password(password),
            first_name=first_name,
            last_name=last_name,
            middle_name=None,
            status=UserStatus.ACTIVE,
            is_superuser=is_superuser,
            role_id=role.id,
            branch_id=branch.id if branch else None,
        )
        session.add(user)
        session.flush()
        return user

    user.username = username
    user.email = email
    user.phone = phone
    user.first_name = first_name
    user.last_name = last_name
    user.middle_name = None
    user.status = UserStatus.ACTIVE
    user.password_hash = hash_password(password)
    user.role_id = role.id
    user.branch_id = branch.id if branch else None
    user.is_superuser = is_superuser
    return user


def get_or_create_rate(
    session: Session,
    *,
    name: str,
    rate_type: PayoutRateType,
    amount: Decimal,
    branch: Branch,
    created_by: User,
    per_unit_name: str | None = None,
) -> PayoutRate:
    rate = session.scalar(select(PayoutRate).where(PayoutRate.name == name))
    if rate is None:
        rate = PayoutRate(
            name=name,
            rate_type=rate_type,
            amount=amount,
            currency="RUB",
            per_unit_name=per_unit_name,
            is_active=True,
            branch_id=branch.id,
            created_by_id=created_by.id,
        )
        session.add(rate)
        session.flush()
    else:
        rate.rate_type = rate_type
        rate.amount = amount
        rate.currency = "RUB"
        rate.per_unit_name = per_unit_name
        rate.is_active = True
        rate.branch_id = branch.id
        rate.created_by_id = created_by.id
    return rate


def build_route_times(work_date: date, start_hour: int, duration_hours: int) -> tuple[datetime, datetime]:
    start_at = datetime.combine(work_date, time(hour=start_hour), tzinfo=UTC)
    end_at = start_at + timedelta(hours=duration_hours)
    return start_at, end_at


def get_or_create_route(
    session: Session,
    *,
    title: str,
    description: str,
    branch: Branch,
    created_by: User,
    promoter: User | None,
    payout_rate: PayoutRate | None,
    work_date: date,
    status: RouteStatus,
    start_hour: int,
    duration_hours: int,
    point_labels: list[tuple[str, str, float, float, RoutePointType]],
) -> Route:
    route = session.scalar(select(Route).where(Route.title == title))
    planned_start_at, planned_end_at = build_route_times(work_date, start_hour, duration_hours)

    if route is None:
        route = Route(
            title=title,
            description=description,
            work_date=work_date,
            planned_start_at=planned_start_at,
            planned_end_at=planned_end_at,
            status=status,
            branch_id=branch.id,
            promoter_id=promoter.id if promoter else None,
            created_by_id=created_by.id,
            payout_rate_id=payout_rate.id if payout_rate else None,
        )
        session.add(route)
        session.flush()
    else:
        route.description = description
        route.work_date = work_date
        route.planned_start_at = planned_start_at
        route.planned_end_at = planned_end_at
        route.status = status
        route.branch_id = branch.id
        route.promoter_id = promoter.id if promoter else None
        route.created_by_id = created_by.id
        route.payout_rate_id = payout_rate.id if payout_rate else None

    existing_points = {point.sequence: point for point in route.points}
    for index, (name, address, latitude, longitude, point_type) in enumerate(point_labels, start=1):
        point = existing_points.get(index)
        planned_arrival_at = planned_start_at + timedelta(minutes=(index - 1) * 50)
        if point is None:
            point = RoutePoint(
                route=route,
                sequence=index,
                name=name,
                address=address,
                latitude=latitude,
                longitude=longitude,
                point_type=point_type,
                planned_arrival_at=planned_arrival_at,
                notes=None,
            )
            session.add(point)
        else:
            point.name = name
            point.address = address
            point.latitude = latitude
            point.longitude = longitude
            point.point_type = point_type
            point.planned_arrival_at = planned_arrival_at
            point.notes = None

    session.flush()
    session.refresh(route)
    return route


def get_or_create_session(
    session: Session,
    *,
    route: Route,
    promoter: User,
    status: PromoterSessionStatus,
    started_at: datetime,
    ended_at: datetime | None,
    total_minutes: int | None,
    leaflet_count: int | None,
    summary: str | None,
) -> PromoterSession:
    route_session = session.scalar(select(PromoterSession).where(PromoterSession.route_id == route.id))
    if route_session is None:
        route_session = PromoterSession(
            route_id=route.id,
            promoter_id=promoter.id,
            status=status,
            started_at=started_at,
            ended_at=ended_at,
            total_minutes=total_minutes,
            leaflet_count=leaflet_count,
            summary=summary,
            started_latitude=route.points[0].latitude if route.points else None,
            started_longitude=route.points[0].longitude if route.points else None,
            finished_latitude=route.points[-1].latitude if ended_at and route.points else None,
            finished_longitude=route.points[-1].longitude if ended_at and route.points else None,
        )
        session.add(route_session)
        session.flush()
        return route_session

    route_session.status = status
    route_session.started_at = started_at
    route_session.ended_at = ended_at
    route_session.total_minutes = total_minutes
    route_session.leaflet_count = leaflet_count
    route_session.summary = summary
    route_session.started_latitude = route.points[0].latitude if route.points else None
    route_session.started_longitude = route.points[0].longitude if route.points else None
    route_session.finished_latitude = route.points[-1].latitude if ended_at and route.points else None
    route_session.finished_longitude = route.points[-1].longitude if ended_at and route.points else None
    return route_session


def ensure_geo_pings(
    session: Session,
    *,
    route: Route,
    route_session: PromoterSession,
    promoter: User,
    points_to_use: list[int],
) -> None:
    existing = list(session.scalars(select(GeoPing).where(GeoPing.session_id == route_session.id)))
    if existing:
        return

    for offset, point_index in enumerate(points_to_use):
        point = route.points[point_index]
        session.add(
            GeoPing(
                session_id=route_session.id,
                route_id=route.id,
                promoter_id=promoter.id,
                point_id=point.id,
                captured_at=(route_session.started_at or datetime.now(UTC)) + timedelta(minutes=offset * 35),
                latitude=point.latitude or 0,
                longitude=point.longitude or 0,
                accuracy_meters=Decimal("12.50"),
                speed_mps=Decimal("0.00"),
                heading_degrees=Decimal("0.00"),
                source=GeoPingSource.START if offset == 0 else GeoPingSource.TRACKING,
                raw_payload={"seed": True, "point": point.name},
            )
        )


def ensure_photo_report(
    session: Session,
    *,
    route: Route,
    route_session: PromoterSession,
    promoter: User,
    reviewer: User | None,
    point_index: int,
    status: PhotoReportStatus,
    notes: str,
) -> None:
    existing = session.scalar(select(PhotoReport).where(PhotoReport.session_id == route_session.id))
    if existing is not None:
        existing.status = status
        existing.notes = notes
        existing.reviewed_by_id = reviewer.id if reviewer else None
        existing.reviewed_at = datetime.now(UTC) if reviewer else None
        return

    point = route.points[point_index]
    session.add(
        PhotoReport(
            route_id=route.id,
            session_id=route_session.id,
            promoter_id=promoter.id,
            point_id=point.id,
            reviewed_by_id=reviewer.id if reviewer else None,
            file_path=f"seed/{route.title.lower().replace(' ', '-')}.jpg",
            thumbnail_path=None,
            captured_at=(route_session.started_at or datetime.now(UTC)) + timedelta(minutes=55),
            latitude=point.latitude,
            longitude=point.longitude,
            notes=notes,
            status=status,
            reviewed_at=datetime.now(UTC) if reviewer else None,
        )
    )


def ensure_payout(
    session: Session,
    *,
    route: Route,
    route_session: PromoterSession,
    promoter: User,
    payout_rate: PayoutRate,
    amount: Decimal,
    units: Decimal,
    status: PayoutStatus,
    notes: str,
    calculation_details: dict,
    approved_by: User | None = None,
) -> None:
    payout = session.scalar(select(Payout).where(Payout.route_id == route.id))
    if payout is None:
        payout = Payout(
            route_id=route.id,
            session_id=route_session.id,
            promoter_id=promoter.id,
            payout_rate_id=payout_rate.id,
            approved_by_id=approved_by.id if approved_by else None,
            amount=amount,
            currency="RUB",
            units=units,
            notes=notes,
            calculation_details=calculation_details,
            status=status,
            calculated_at=datetime.now(UTC),
            approved_at=datetime.now(UTC) if approved_by else None,
        )
        session.add(payout)
        return

    payout.session_id = route_session.id
    payout.promoter_id = promoter.id
    payout.payout_rate_id = payout_rate.id
    payout.approved_by_id = approved_by.id if approved_by else None
    payout.amount = amount
    payout.currency = "RUB"
    payout.units = units
    payout.notes = notes
    payout.calculation_details = calculation_details
    payout.status = status
    payout.calculated_at = datetime.now(UTC)
    payout.approved_at = datetime.now(UTC) if approved_by else None


def ensure_notification(
    session: Session,
    *,
    user: User,
    title: str,
    body: str,
    payload: dict | None = None,
    status: NotificationStatus = NotificationStatus.PENDING,
) -> None:
    notification = session.scalar(
        select(Notification).where(Notification.user_id == user.id, Notification.title == title)
    )
    if notification is None:
        notification = Notification(
            user_id=user.id,
            title=title,
            body=body,
            channel=NotificationChannel.IN_APP,
            status=status,
            payload=payload,
            scheduled_at=None,
            sent_at=datetime.now(UTC),
            read_at=datetime.now(UTC) if status == NotificationStatus.READ else None,
        )
        session.add(notification)
        return

    notification.body = body
    notification.channel = NotificationChannel.IN_APP
    notification.status = status
    notification.payload = payload
    notification.sent_at = datetime.now(UTC)
    notification.read_at = datetime.now(UTC) if status == NotificationStatus.READ else None


def ensure_audit_log(
    session: Session,
    *,
    actor: User,
    branch: Branch | None,
    entity_type: str,
    entity_id: str,
    action: str,
    payload: dict | None = None,
) -> None:
    existing = session.scalar(
        select(AuditLog).where(
            AuditLog.entity_type == entity_type,
            AuditLog.entity_id == entity_id,
            AuditLog.action == action,
        )
    )
    if existing is not None:
        existing.actor_user_id = actor.id
        existing.branch_id = branch.id if branch else None
        existing.payload = payload
        return

    session.add(
        AuditLog(
            actor_user_id=actor.id,
            branch_id=branch.id if branch else None,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            ip_address="127.0.0.1",
            user_agent="seed-script",
            payload=payload,
            created_at=datetime.now(UTC),
        )
    )


def ensure_master_request(
    session: Session,
    *,
    title: str,
    description: str,
    branch: Branch,
    requester: User,
    assignee: User | None,
    status: MasterRequestStatus,
    address: str,
    client_name: str,
    client_phone: str,
    estimated_amount: Decimal,
    final_amount: Decimal | None = None,
) -> MasterRequest:
    request_obj = session.scalar(select(MasterRequest).where(MasterRequest.title == title))
    geo_enabled = status in {MasterRequestStatus.ON_THE_WAY, MasterRequestStatus.IN_PROGRESS}

    if request_obj is None:
        request_obj = MasterRequest(
            branch_id=branch.id,
            requester_id=requester.id,
            assignee_id=assignee.id if assignee else None,
            title=title,
            description=description,
            address=address,
            client_name=client_name,
            client_phone=client_phone,
            estimated_amount=estimated_amount,
            final_amount=final_amount,
            currency="RUB",
            status=status,
            geo_tracking_enabled=geo_enabled,
            requested_at=datetime.now(UTC) - timedelta(hours=4),
            accepted_at=(
                datetime.now(UTC) - timedelta(hours=3)
                if status != MasterRequestStatus.NEW
                else None
            ),
            started_at=(
                datetime.now(UTC) - timedelta(hours=2)
                if status in {
                    MasterRequestStatus.ON_THE_WAY,
                    MasterRequestStatus.IN_PROGRESS,
                    MasterRequestStatus.COMPLETED,
                    MasterRequestStatus.HANDED_OVER,
                }
                else None
            ),
            completed_at=(
                datetime.now(UTC) - timedelta(hours=1)
                if status in {MasterRequestStatus.COMPLETED, MasterRequestStatus.HANDED_OVER}
                else None
            ),
            handed_over_at=(
                datetime.now(UTC)
                if status == MasterRequestStatus.HANDED_OVER
                else None
            ),
            last_known_latitude=Decimal("55.7579") if geo_enabled else None,
            last_known_longitude=Decimal("37.6156") if geo_enabled else None,
            last_known_at=datetime.now(UTC) if geo_enabled else None,
        )
        session.add(request_obj)
        session.flush()

        session.add(
            MasterRequestStatusLog(
                master_request_id=request_obj.id,
                changed_by_id=requester.id,
                from_status=None,
                to_status=MasterRequestStatus.NEW,
                note="Заявка создана",
                created_at=request_obj.requested_at or datetime.now(UTC),
            )
        )
        if status != MasterRequestStatus.NEW:
            session.add(
                MasterRequestStatusLog(
                    master_request_id=request_obj.id,
                    changed_by_id=assignee.id if assignee else requester.id,
                    from_status=MasterRequestStatus.NEW,
                    to_status=status,
                    note="Демо-переход статуса",
                    created_at=datetime.now(UTC) - timedelta(minutes=30),
                )
            )

        session.add(
            MasterRequestComment(
                master_request_id=request_obj.id,
                author_id=requester.id,
                body="Клиент готов принять мастера в течение часа.",
            )
        )
    else:
        request_obj.description = description
        request_obj.assignee_id = assignee.id if assignee else None
        request_obj.status = status
        request_obj.geo_tracking_enabled = geo_enabled
        request_obj.address = address
        request_obj.client_name = client_name
        request_obj.client_phone = client_phone
        request_obj.estimated_amount = estimated_amount
        request_obj.final_amount = final_amount

    session.flush()
    return request_obj


def ensure_expense_plan(
    session: Session,
    *,
    title: str,
    branch: Branch,
    created_by: User,
    period_start: date,
    period_end: date,
    status: ExpensePlanStatus,
    items_data: list[tuple[str, str, Decimal, Decimal]],
    approver: User | None = None,
    decision: ExpenseApprovalDecision = ExpenseApprovalDecision.PENDING,
) -> ExpensePlan:
    plan = session.scalar(select(ExpensePlan).where(ExpensePlan.title == title))
    total = sum((qty * price for _, _, qty, price in items_data), Decimal("0"))

    if plan is None:
        plan = ExpensePlan(
            branch_id=branch.id,
            created_by_id=created_by.id,
            title=title,
            period_start=period_start,
            period_end=period_end,
            total_amount=total,
            currency="RUB",
            status=status,
            comment="Демо-план для проверки согласования.",
            submitted_at=(
                datetime.now(UTC) - timedelta(hours=2)
                if status != ExpensePlanStatus.DRAFT
                else None
            ),
            approved_at=(
                datetime.now(UTC) - timedelta(hours=1)
                if status == ExpensePlanStatus.APPROVED
                else None
            ),
        )
        session.add(plan)
        session.flush()

        for index, (name, category, qty, price) in enumerate(items_data, start=1):
            session.add(
                ExpensePlanItem(
                    expense_plan_id=plan.id,
                    sequence=index,
                    name=name,
                    category=category,
                    quantity=qty,
                    unit_price=price,
                    amount=qty * price,
                    note=None,
                )
            )

        if approver is not None and status != ExpensePlanStatus.DRAFT:
            session.add(
                ExpenseApproval(
                    expense_plan_id=plan.id,
                    approver_id=approver.id,
                    decision=decision,
                    comment=(
                        "Согласовано в демо-данных"
                        if decision == ExpenseApprovalDecision.APPROVED
                        else None
                    ),
                    decided_at=(
                        datetime.now(UTC) - timedelta(hours=1)
                        if decision != ExpenseApprovalDecision.PENDING
                        else None
                    ),
                )
            )
    else:
        plan.total_amount = total
        plan.status = status

    session.flush()
    return plan


def main() -> None:
    session = SessionLocal()
    try:
        owner_role = get_or_create_role(session, RoleCode.OWNER, "Собственник", "Полный доступ ко всей системе")
        branch_manager_role = get_or_create_role(
            session,
            RoleCode.BRANCH_MANAGER,
            "Руководитель филиала",
            "Управляет пользователями и маршрутами своего филиала",
        )
        ad_director_role = get_or_create_role(
            session,
            RoleCode.AD_DIRECTOR,
            "Директор по рекламе",
            "Отвечает за рекламные маршруты и фотоотчёты",
        )
        master_role = get_or_create_role(
            session,
            RoleCode.MASTER,
            "Мастер",
            "Полевой исполнитель сервисных задач",
        )
        promoter_role = get_or_create_role(
            session,
            RoleCode.PROMOTER,
            "Промоутер",
            "Исполнитель маршрутов",
        )
        dispatcher_role = get_or_create_role(
            session,
            RoleCode.DISPATCHER,
            "Диспетчер",
            "Принимает заявки клиентов, создаёт и распределяет маршруты",
        )

        center_branch = get_or_create_branch(
            session,
            code="demo-msk-center",
            name="Москва Центр",
            city="Москва",
            address="ул. Тверская, 7",
        )
        north_branch = get_or_create_branch(
            session,
            code="demo-msk-north",
            name="Москва Север",
            city="Москва",
            address="Ленинградский проспект, 12",
        )

        owner = get_or_create_user(
            session,
            username="owner.demo",
            email="owner.demo@promouters.local",
            phone="+79990000001",
            first_name="Ольга",
            last_name="Собственник",
            role=owner_role,
            branch=center_branch,
            is_superuser=True,
        )
        center_manager = get_or_create_user(
            session,
            username="manager.center",
            email="manager.center@promouters.local",
            phone="+79990000002",
            first_name="Игорь",
            last_name="Центровой",
            role=branch_manager_role,
            branch=center_branch,
        )
        center_director = get_or_create_user(
            session,
            username="director.center",
            email="director.center@promouters.local",
            phone="+79990000003",
            first_name="Мария",
            last_name="Рекламова",
            role=ad_director_role,
            branch=center_branch,
        )
        center_promoter = get_or_create_user(
            session,
            username="promoter.center",
            email="promoter.center@promouters.local",
            phone="+79990000004",
            first_name="Алина",
            last_name="Промо",
            role=promoter_role,
            branch=center_branch,
        )
        north_manager = get_or_create_user(
            session,
            username="manager.north",
            email="manager.north@promouters.local",
            phone="+79990000005",
            first_name="Никита",
            last_name="Северный",
            role=branch_manager_role,
            branch=north_branch,
        )
        north_promoter = get_or_create_user(
            session,
            username="promoter.north",
            email="promoter.north@promouters.local",
            phone="+79990000006",
            first_name="Ева",
            last_name="Полярная",
            role=promoter_role,
            branch=north_branch,
        )
        get_or_create_user(
            session,
            username="master.center",
            email="master.center@promouters.local",
            phone="+79990000007",
            first_name="Сергей",
            last_name="Мастеровой",
            role=master_role,
            branch=center_branch,
        )
        get_or_create_user(
            session,
            username="dispatcher.demo",
            email="dispatcher.demo@promouters.local",
            phone="+79990000008",
            first_name="Анна",
            last_name="Диспетчер",
            role=dispatcher_role,
            branch=center_branch,
        )
        master_user = session.scalar(select(User).where(User.username == "master.center"))
        assert master_user is not None

        hourly_rate = get_or_create_rate(
            session,
            name="Демо ставка почасовая",
            rate_type=PayoutRateType.HOURLY,
            amount=Decimal("18.00"),
            branch=center_branch,
            created_by=owner,
            per_unit_name="hour",
        )
        leaflet_rate = get_or_create_rate(
            session,
            name="Демо ставка за листовку",
            rate_type=PayoutRateType.PER_LEAFLET,
            amount=Decimal("0.70"),
            branch=center_branch,
            created_by=owner,
            per_unit_name="leaflet",
        )
        fixed_shift_rate = get_or_create_rate(
            session,
            name="Демо фикс за смену",
            rate_type=PayoutRateType.FIXED_SHIFT,
            amount=Decimal("65.00"),
            branch=north_branch,
            created_by=owner,
            per_unit_name="shift",
        )

        today = date.today()
        yesterday = today - timedelta(days=1)
        two_days_ago = today - timedelta(days=2)

        center_points = [
            ("Старт у офиса", "ул. Тверская, 7", 55.7579, 37.6156, RoutePointType.START),
            ("ТЦ Охотный Ряд", "Манежная площадь, 1", 55.7562, 37.6156, RoutePointType.CHECKPOINT),
            ("Финиш у Пушкинской", "Пушкинская площадь, 2", 55.7659, 37.6056, RoutePointType.FINISH),
        ]
        north_points = [
            ("Старт у филиала", "Ленинградский проспект, 12", 55.7999, 37.5386, RoutePointType.START),
            ("ТЦ Авиапарк", "Ходынский бульвар, 4", 55.7908, 37.5316, RoutePointType.CHECKPOINT),
            ("Финиш у метро Динамо", "Ленинградский проспект, 36", 55.7897, 37.5582, RoutePointType.FINISH),
        ]

        draft_route = get_or_create_route(
            session,
            title="Центр: завтрашний черновик",
            description="Черновой маршрут для проверки создания и редактирования.",
            branch=center_branch,
            created_by=center_manager,
            promoter=None,
            payout_rate=hourly_rate,
            work_date=today + timedelta(days=1),
            status=RouteStatus.DRAFT,
            start_hour=10,
            duration_hours=4,
            point_labels=center_points,
        )
        assigned_route = get_or_create_route(
            session,
            title="Центр: назначенная смена",
            description="Маршрут назначен промоутеру и ожидает старта.",
            branch=center_branch,
            created_by=center_manager,
            promoter=center_promoter,
            payout_rate=hourly_rate,
            work_date=today,
            status=RouteStatus.ASSIGNED,
            start_hour=9,
            duration_hours=4,
            point_labels=center_points,
        )
        active_route = get_or_create_route(
            session,
            title="Центр: активная смена",
            description="Маршрут в процессе выполнения, есть GPS и незавершённый фотоотчёт.",
            branch=center_branch,
            created_by=center_director,
            promoter=center_promoter,
            payout_rate=hourly_rate,
            work_date=today,
            status=RouteStatus.IN_PROGRESS,
            start_hour=11,
            duration_hours=3,
            point_labels=center_points,
        )
        completed_leaflet_route = get_or_create_route(
            session,
            title="Центр: завершённый маршрут по листовкам",
            description="Готовый сценарий для фотоотчёта и выплаты по листовкам.",
            branch=center_branch,
            created_by=center_director,
            promoter=center_promoter,
            payout_rate=leaflet_rate,
            work_date=yesterday,
            status=RouteStatus.COMPLETED,
            start_hour=10,
            duration_hours=3,
            point_labels=center_points,
        )
        completed_hourly_route = get_or_create_route(
            session,
            title="Центр: завершённый почасовой маршрут",
            description="Готовый сценарий для расчёта выплаты по времени.",
            branch=center_branch,
            created_by=center_manager,
            promoter=center_promoter,
            payout_rate=hourly_rate,
            work_date=two_days_ago,
            status=RouteStatus.COMPLETED,
            start_hour=12,
            duration_hours=4,
            point_labels=center_points,
        )
        north_assigned_route = get_or_create_route(
            session,
            title="Север: маршрут другого филиала",
            description="Маршрут второго филиала для проверки разграничения доступа.",
            branch=north_branch,
            created_by=north_manager,
            promoter=north_promoter,
            payout_rate=fixed_shift_rate,
            work_date=today,
            status=RouteStatus.ASSIGNED,
            start_hour=13,
            duration_hours=3,
            point_labels=north_points,
        )

        active_session = get_or_create_session(
            session,
            route=active_route,
            promoter=center_promoter,
            status=PromoterSessionStatus.ACTIVE,
            started_at=datetime.now(UTC) - timedelta(hours=1, minutes=20),
            ended_at=None,
            total_minutes=None,
            leaflet_count=None,
            summary="Смена в процессе выполнения.",
        )
        completed_leaflet_session = get_or_create_session(
            session,
            route=completed_leaflet_route,
            promoter=center_promoter,
            status=PromoterSessionStatus.COMPLETED,
            started_at=datetime.now(UTC) - timedelta(days=1, hours=4),
            ended_at=datetime.now(UTC) - timedelta(days=1, hours=1),
            total_minutes=180,
            leaflet_count=450,
            summary="Маршрут завершён, фотоотчёты загружены, листовки пересчитаны.",
        )
        completed_hourly_session = get_or_create_session(
            session,
            route=completed_hourly_route,
            promoter=center_promoter,
            status=PromoterSessionStatus.COMPLETED,
            started_at=datetime.now(UTC) - timedelta(days=2, hours=5),
            ended_at=datetime.now(UTC) - timedelta(days=2, hours=1),
            total_minutes=240,
            leaflet_count=0,
            summary="Почасовой маршрут завершён без замечаний.",
        )

        ensure_geo_pings(
            session,
            route=active_route,
            route_session=active_session,
            promoter=center_promoter,
            points_to_use=[0, 1],
        )
        ensure_geo_pings(
            session,
            route=completed_leaflet_route,
            route_session=completed_leaflet_session,
            promoter=center_promoter,
            points_to_use=[0, 1, 2],
        )
        ensure_photo_report(
            session,
            route=completed_leaflet_route,
            route_session=completed_leaflet_session,
            promoter=center_promoter,
            reviewer=center_manager,
            point_index=1,
            status=PhotoReportStatus.ACCEPTED,
            notes="Фотоотчёт принят руководителем филиала.",
        )
        ensure_photo_report(
            session,
            route=active_route,
            route_session=active_session,
            promoter=center_promoter,
            reviewer=None,
            point_index=1,
            status=PhotoReportStatus.PENDING,
            notes="Промежуточный кадр ожидает проверки.",
        )

        ensure_payout(
            session,
            route=completed_leaflet_route,
            route_session=completed_leaflet_session,
            promoter=center_promoter,
            payout_rate=leaflet_rate,
            amount=Decimal("315.00"),
            units=Decimal("450.00"),
            status=PayoutStatus.CALCULATED,
            notes="450 листовок по 0.70 RUB",
            calculation_details={"rate_type": "per_leaflet", "leaflet_count": 450, "rate_amount": "0.70"},
        )
        ensure_payout(
            session,
            route=completed_hourly_route,
            route_session=completed_hourly_session,
            promoter=center_promoter,
            payout_rate=hourly_rate,
            amount=Decimal("72.00"),
            units=Decimal("4.00"),
            status=PayoutStatus.APPROVED,
            notes="4 часа по 18 RUB",
            calculation_details={"rate_type": "hourly", "hours": 4, "rate_amount": "18.00"},
            approved_by=owner,
        )

        ensure_notification(
            session,
            user=center_promoter,
            title="Назначен маршрут",
            body="Вам назначена смена «Центр: назначенная смена».",
            payload={"route_title": assigned_route.title},
        )
        ensure_notification(
            session,
            user=center_promoter,
            title="Напоминание о фотоотчёте",
            body="По активной смене ещё нужен финальный фотоотчёт.",
            payload={"route_title": active_route.title},
        )
        ensure_notification(
            session,
            user=center_manager,
            title="Маршрут завершён",
            body="Промоутер завершил маршрут по листовкам, выплата рассчитана.",
            payload={"route_title": completed_leaflet_route.title},
        )
        ensure_notification(
            session,
            user=owner,
            title="Обновлены демо-данные",
            body="В системе подготовлены тестовые маршруты, выплаты и уведомления для UAT.",
            payload={"branches": [center_branch.name, north_branch.name]},
            status=NotificationStatus.READ,
        )

        ensure_audit_log(
            session,
            actor=center_manager,
            branch=center_branch,
            entity_type="route",
            entity_id=str(draft_route.id),
            action="route.created",
            payload={"title": draft_route.title},
        )
        ensure_audit_log(
            session,
            actor=center_manager,
            branch=center_branch,
            entity_type="route",
            entity_id=str(assigned_route.id),
            action="route.assigned",
            payload={"promoter": center_promoter.username},
        )
        ensure_audit_log(
            session,
            actor=owner,
            branch=center_branch,
            entity_type="payout_rate",
            entity_id=str(hourly_rate.id),
            action="payout_rate.updated",
            payload={"name": hourly_rate.name, "amount": str(hourly_rate.amount)},
        )
        ensure_audit_log(
            session,
            actor=north_manager,
            branch=north_branch,
            entity_type="route",
            entity_id=str(north_assigned_route.id),
            action="route.created",
            payload={"title": north_assigned_route.title},
        )
        ensure_audit_log(
            session,
            actor=center_promoter,
            branch=center_branch,
            entity_type="route_report",
            entity_id=str(completed_leaflet_route.id),
            action="route.report.completed",
            payload={"route_title": completed_leaflet_route.title},
        )

        # Демо-заявки мастеру
        ensure_master_request(
            session,
            title="Установка кондиционера у клиента",
            description="Демонтаж старого блока, установка нового.",
            branch=center_branch,
            requester=center_director,
            assignee=master_user,
            status=MasterRequestStatus.IN_PROGRESS,
            address="ул. Тверская, 18",
            client_name="ООО Ромашка",
            client_phone="+74950001122",
            estimated_amount=Decimal("12000.00"),
        )
        ensure_master_request(
            session,
            title="Срочный ремонт оборудования",
            description="Перезапуск принтера и проверка платы.",
            branch=center_branch,
            requester=center_manager,
            assignee=master_user,
            status=MasterRequestStatus.NEW,
            address="Манежная площадь, 1",
            client_name="Кафе Восход",
            client_phone="+74950003344",
            estimated_amount=Decimal("4500.00"),
        )
        ensure_master_request(
            session,
            title="Сданная заявка с БСО",
            description="Заявка завершена, БСО передан на склад.",
            branch=center_branch,
            requester=center_director,
            assignee=master_user,
            status=MasterRequestStatus.HANDED_OVER,
            address="Пушкинская площадь, 5",
            client_name="Студия Ясного",
            client_phone="+74950005566",
            estimated_amount=Decimal("8000.00"),
            final_amount=Decimal("8500.00"),
        )

        # Демо-планы расходов
        ensure_expense_plan(
            session,
            title="Центр: план на месяц",
            branch=center_branch,
            created_by=center_manager,
            period_start=today.replace(day=1),
            period_end=today + timedelta(days=20),
            status=ExpensePlanStatus.SUBMITTED,
            items_data=[
                ("Аренда офиса", "Аренда", Decimal("1"), Decimal("60000.00")),
                ("Листовки A5", "Материалы", Decimal("5000"), Decimal("3.20")),
                ("Стойки промо", "Материалы", Decimal("2"), Decimal("4500.00")),
            ],
            approver=owner,
        )
        ensure_expense_plan(
            session,
            title="Север: план согласован",
            branch=north_branch,
            created_by=north_manager,
            period_start=today.replace(day=1),
            period_end=today + timedelta(days=20),
            status=ExpensePlanStatus.APPROVED,
            items_data=[
                ("Аренда офиса", "Аренда", Decimal("1"), Decimal("48000.00")),
                ("Листовки A6", "Материалы", Decimal("3000"), Decimal("2.10")),
            ],
            approver=owner,
            decision=ExpenseApprovalDecision.APPROVED,
        )

        session.commit()

        print("Seed complete.")
        print("Demo accounts:")
        print(f"  owner.demo / {DEFAULT_PASSWORD} / +79990000001")
        print(f"  manager.center / {DEFAULT_PASSWORD} / +79990000002")
        print(f"  director.center / {DEFAULT_PASSWORD} / +79990000003")
        print(f"  promoter.center / {DEFAULT_PASSWORD} / +79990000004")
        print(f"  manager.north / {DEFAULT_PASSWORD} / +79990000005")
        print(f"  promoter.north / {DEFAULT_PASSWORD} / +79990000006")
        print(f"  master.center / {DEFAULT_PASSWORD} / +79990000007")
        print(f"  dispatcher.demo / {DEFAULT_PASSWORD} / +79990000008")
    finally:
        session.close()


if __name__ == "__main__":
    main()
