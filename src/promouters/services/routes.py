from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Iterable
from uuid import UUID, uuid4

from fastapi import HTTPException, Request, UploadFile, status
from sqlalchemy import Select, select
from sqlalchemy.orm import Session, joinedload, selectinload

from promouters.core.config import Settings
from promouters.models.enums import (
    GeoPingSource,
    PhotoReportStatus,
    PromoterReportReviewStatus,
    PromoterSessionStatus,
    RoleCode,
    RoutePointType,
    RouteStatus,
    UserStatus,
)
from promouters.models.finance import Payout, PayoutRate
from promouters.models.routing import GeoPing, PhotoReport, PromoterSession, Route, RoutePoint
from promouters.models.users import Branch, User
from promouters.schemas.routes import (
    AvailablePromoterRead,
    GeoPingCreate,
    GeoPingRead,
    PhotoReportRead,
    PhotoReviewRequest,
    PromoterReportReviewRequest,
    PromoterSessionRead,
    RouteAssignRequest,
    RouteCreate,
    RouteFinishRequest,
    RoutePointInput,
    RoutePointRead,
    RouteRead,
    RouteReportRead,
    RouteStartRequest,
    RouteUpdate,
)
from promouters.services.access import (
    ensure_same_branch,
    get_role_code,
    is_owner,
    is_route_manager,
    require_branch_assignment,
)
from promouters.services.audit import write_audit_log
from promouters.services.finance import calculate_payout_for_route, to_payout_read
from promouters.services.notifications import (
    notify_owners_about_key_change,
    notify_route_assignment,
    notify_route_completed_to_managers,
)


def as_float(value: Decimal | float | None) -> float | None:
    if value is None:
        return None
    return float(value)


def full_name(user: User | None) -> str | None:
    if user is None:
        return None
    return " ".join(part for part in [user.first_name, user.last_name] if part).strip() or user.username


def media_file_url(settings: Settings, relative_path: str) -> str:
    base_url = settings.media_url.rstrip("/")
    return f"{base_url}/{relative_path.replace('\\', '/')}"


def route_query() -> Select[tuple[Route]]:
    return (
        select(Route)
        .options(
            joinedload(Route.branch),
            joinedload(Route.promoter).joinedload(User.branch),
            joinedload(Route.created_by),
            selectinload(Route.points),
            selectinload(Route.sessions).selectinload(PromoterSession.geo_pings),
            selectinload(Route.sessions).selectinload(PromoterSession.photo_reports),
            selectinload(Route.sessions).selectinload(PromoterSession.payouts),
            selectinload(Route.photo_reports).joinedload(PhotoReport.promoter),
            selectinload(Route.payouts).joinedload(Payout.payout_rate),
            selectinload(Route.payouts).joinedload(Payout.promoter),
        )
    )


def session_query() -> Select[tuple[PromoterSession]]:
    return (
        select(PromoterSession)
        .options(
            joinedload(PromoterSession.route).joinedload(Route.branch),
            joinedload(PromoterSession.route).joinedload(Route.promoter),
            joinedload(PromoterSession.promoter).joinedload(User.branch),
            selectinload(PromoterSession.geo_pings).joinedload(GeoPing.point),
            selectinload(PromoterSession.photo_reports).joinedload(PhotoReport.point),
            selectinload(PromoterSession.photo_reports).joinedload(PhotoReport.promoter),
            selectinload(PromoterSession.payouts).joinedload(Payout.payout_rate),
        )
    )


def photo_query() -> Select[tuple[PhotoReport]]:
    return (
        select(PhotoReport)
        .options(
            joinedload(PhotoReport.route).joinedload(Route.branch),
            joinedload(PhotoReport.session),
            joinedload(PhotoReport.promoter),
            joinedload(PhotoReport.point),
            joinedload(PhotoReport.reviewed_by),
        )
    )


def geo_ping_query() -> Select[tuple[GeoPing]]:
    return select(GeoPing).options(joinedload(GeoPing.point), joinedload(GeoPing.session))


def _serialize_route(route: Route, settings: Settings) -> dict:
    return to_route_read(route, settings).model_dump(mode="json")


def _serialize_session(session: PromoterSession) -> dict:
    return to_promoter_session_read(session).model_dump(mode="json")


def _serialize_photo(photo: PhotoReport, settings: Settings) -> dict:
    return to_photo_report_read(photo, settings).model_dump(mode="json")


def to_route_point_read(point: RoutePoint) -> RoutePointRead:
    return RoutePointRead(
        id=point.id,
        route_id=point.route_id,
        sequence=point.sequence,
        name=point.name,
        address=point.address,
        latitude=as_float(point.latitude),
        longitude=as_float(point.longitude),
        point_type=point.point_type.value,
        planned_arrival_at=point.planned_arrival_at,
        notes=point.notes,
        created_at=point.created_at,
        updated_at=point.updated_at,
    )


def to_promoter_session_read(session: PromoterSession) -> PromoterSessionRead:
    return PromoterSessionRead(
        id=session.id,
        route_id=session.route_id,
        promoter_id=session.promoter_id,
        promoter_name=full_name(session.promoter) or "",
        status=session.status.value,
        started_at=session.started_at,
        ended_at=session.ended_at,
        total_minutes=session.total_minutes,
        leaflet_count=session.leaflet_count,
        summary=session.summary,
        started_latitude=as_float(session.started_latitude),
        started_longitude=as_float(session.started_longitude),
        finished_latitude=as_float(session.finished_latitude),
        finished_longitude=as_float(session.finished_longitude),
        photo_count=len(session.photo_reports),
        geo_ping_count=len(session.geo_pings),
        review_status=session.review_status.value,
        review_comment=session.review_comment,
        accepted_by_director_id=session.accepted_by_director_id,
        accepted_by_director_name=full_name(session.accepted_by_director) if session.accepted_by_director else None,
        accepted_at=session.accepted_at,
        forwarded_by_id=session.forwarded_by_id,
        forwarded_by_name=full_name(session.forwarded_by) if session.forwarded_by else None,
        forwarded_at=session.forwarded_at,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


def to_geo_ping_read(geo_ping: GeoPing) -> GeoPingRead:
    return GeoPingRead(
        id=geo_ping.id,
        session_id=geo_ping.session_id,
        route_id=geo_ping.route_id,
        promoter_id=geo_ping.promoter_id,
        point_id=geo_ping.point_id,
        point_name=geo_ping.point.name if geo_ping.point else None,
        captured_at=geo_ping.captured_at,
        latitude=as_float(geo_ping.latitude) or 0.0,
        longitude=as_float(geo_ping.longitude) or 0.0,
        accuracy_meters=as_float(geo_ping.accuracy_meters),
        speed_mps=as_float(geo_ping.speed_mps),
        heading_degrees=as_float(geo_ping.heading_degrees),
        source=geo_ping.source.value,
    )


def to_photo_report_read(photo: PhotoReport, settings: Settings) -> PhotoReportRead:
    return PhotoReportRead(
        id=photo.id,
        route_id=photo.route_id,
        session_id=photo.session_id,
        promoter_id=photo.promoter_id,
        promoter_name=full_name(photo.promoter) or "",
        point_id=photo.point_id,
        point_name=photo.point.name if photo.point else None,
        reviewed_by_id=photo.reviewed_by_id,
        reviewed_by_name=full_name(photo.reviewed_by),
        file_path=photo.file_path,
        file_url=media_file_url(settings, photo.file_path),
        thumbnail_path=photo.thumbnail_path,
        captured_at=photo.captured_at,
        latitude=as_float(photo.latitude),
        longitude=as_float(photo.longitude),
        notes=photo.notes,
        status=photo.status.value,
        reviewed_at=photo.reviewed_at,
        created_at=photo.created_at,
        updated_at=photo.updated_at,
    )


def _get_route_session(route: Route) -> PromoterSession | None:
    if not route.sessions:
        return None
    return sorted(route.sessions, key=lambda item: item.created_at, reverse=True)[0]


def to_route_read(route: Route, settings: Settings) -> RouteRead:
    current_session = _get_route_session(route)
    return RouteRead(
        id=route.id,
        title=route.title,
        description=route.description,
        map_image_path=route.map_image_path,
        map_image_url=media_file_url(settings, route.map_image_path) if route.map_image_path else None,
        work_date=route.work_date,
        planned_start_at=route.planned_start_at,
        planned_end_at=route.planned_end_at,
        status=route.status.value,
        branch_id=route.branch_id,
        branch_name=route.branch.name,
        promoter_id=route.promoter_id,
        promoter_name=full_name(route.promoter),
        created_by_id=route.created_by_id,
        created_by_name=full_name(route.created_by) or route.created_by.username,
        payout_rate_id=route.payout_rate_id,
        current_session=to_promoter_session_read(current_session) if current_session else None,
        points=[to_route_point_read(point) for point in sorted(route.points, key=lambda item: item.sequence)],
        photo_count=len(route.photo_reports),
        geo_ping_count=len(current_session.geo_pings) if current_session else 0,
        created_at=route.created_at,
        updated_at=route.updated_at,
    )


def to_available_promoter_read(user: User) -> AvailablePromoterRead:
    return AvailablePromoterRead(
        id=user.id,
        full_name=full_name(user) or user.username,
        branch_id=user.branch_id,
        branch_name=user.branch.name if user.branch else None,
        status=user.status.value,
    )


def get_route_or_404(db: Session, route_id: UUID) -> Route:
    route = db.scalar(route_query().where(Route.id == route_id))
    if route is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Route not found")
    return route


def get_session_or_404(db: Session, session_id: UUID) -> PromoterSession:
    session = db.scalar(session_query().where(PromoterSession.id == session_id))
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Route session not found")
    return session


def get_photo_or_404(db: Session, photo_id: UUID) -> PhotoReport:
    photo = db.scalar(photo_query().where(PhotoReport.id == photo_id))
    if photo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo report not found")
    return photo


def _ensure_manageable_branch(actor_user: User, branch_id: UUID) -> None:
    if is_owner(actor_user):
        return
    ensure_same_branch(actor_user, branch_id)


def _ensure_route_manager(actor_user: User) -> None:
    if not is_route_manager(actor_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")


def _ensure_route_visibility(actor_user: User, route: Route) -> None:
    role_code = get_role_code(actor_user)

    if role_code == RoleCode.OWNER:
        return

    if role_code in {RoleCode.BRANCH_MANAGER, RoleCode.AD_DIRECTOR}:
        ensure_same_branch(actor_user, route.branch_id)
        return

    if role_code == RoleCode.PROMOTER and route.promoter_id == actor_user.id:
        return

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")


def _ensure_session_visibility(actor_user: User, session: PromoterSession) -> None:
    route = session.route
    if route is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Route is not loaded")
    _ensure_route_visibility(actor_user, route)


def _ensure_coordinate_range(latitude: float, longitude: float) -> None:
    if not (-90 <= latitude <= 90):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Latitude is out of range")
    if not (-180 <= longitude <= 180):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Longitude is out of range")


def _validate_route_points(points: Iterable[RoutePointInput]) -> list[RoutePointInput]:
    ordered_points = sorted(points, key=lambda point: point.sequence)
    if len(ordered_points) < 2:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Route must contain at least start and finish points",
        )

    seen_sequences: set[int] = set()
    for point in ordered_points:
        if point.sequence in seen_sequences:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Route point sequences must be unique",
            )
        seen_sequences.add(point.sequence)

        if point.latitude is not None and point.longitude is not None:
            _ensure_coordinate_range(point.latitude, point.longitude)
        elif point.latitude is not None or point.longitude is not None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Point latitude and longitude must be provided together",
            )

    if ordered_points[0].point_type != RoutePointType.START:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The first route point must be a start point",
        )
    if ordered_points[-1].point_type != RoutePointType.FINISH:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The last route point must be a finish point",
        )

    return ordered_points


def _get_payout_rate_or_404(db: Session, payout_rate_id: UUID) -> PayoutRate:
    payout_rate = db.get(PayoutRate, payout_rate_id)
    if payout_rate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payout rate not found")
    return payout_rate


def _ensure_payout_rate_scope(db: Session, payout_rate_id: UUID | None, branch_id: UUID) -> None:
    if payout_rate_id is None:
        return

    payout_rate = _get_payout_rate_or_404(db, payout_rate_id)
    if payout_rate.branch_id is not None and payout_rate.branch_id != branch_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Payout rate belongs to another branch",
        )


def _get_assignable_promoter_or_404(db: Session, promoter_id: UUID, branch_id: UUID) -> User:
    promoter = db.scalar(
        select(User)
        .options(joinedload(User.role), joinedload(User.branch))
        .where(User.id == promoter_id)
    )
    if promoter is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Promoter not found")
    if promoter.branch_id != branch_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Promoter belongs to another branch")
    if promoter.status != UserStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Promoter is not active")
    if get_role_code(promoter) != RoleCode.PROMOTER:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="User is not a promoter")
    return promoter


def _build_route_points(route_id: UUID, points: list[RoutePointInput]) -> list[RoutePoint]:
    ordered_points = _validate_route_points(points)
    return [
        RoutePoint(
            route_id=route_id,
            sequence=point.sequence,
            name=point.name,
            address=point.address,
            latitude=point.latitude,
            longitude=point.longitude,
            point_type=point.point_type,
            planned_arrival_at=point.planned_arrival_at,
            notes=point.notes,
        )
        for point in ordered_points
    ]


def _replace_route_points(route: Route, points: list[RoutePointInput]) -> None:
    ordered_points = _validate_route_points(points)
    route.points[:] = [
        RoutePoint(
            route_id=route.id,
            sequence=point.sequence,
            name=point.name,
            address=point.address,
            latitude=point.latitude,
            longitude=point.longitude,
            point_type=point.point_type,
            planned_arrival_at=point.planned_arrival_at,
            notes=point.notes,
        )
        for point in ordered_points
    ]


def list_routes_for_actor(
    db: Session,
    actor_user: User,
    *,
    route_status: RouteStatus | None = None,
) -> list[Route]:
    stmt = route_query().order_by(Route.work_date.desc(), Route.created_at.desc())
    role_code = get_role_code(actor_user)

    if role_code == RoleCode.OWNER:
        pass
    elif role_code in {RoleCode.BRANCH_MANAGER, RoleCode.AD_DIRECTOR}:
        stmt = stmt.where(Route.branch_id == require_branch_assignment(actor_user))
    elif role_code == RoleCode.PROMOTER:
        stmt = stmt.where(Route.promoter_id == actor_user.id)
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    if route_status is not None:
        stmt = stmt.where(Route.status == route_status)

    return list(db.scalars(stmt))


def get_route_for_actor(db: Session, actor_user: User, route_id: UUID) -> Route:
    route = get_route_or_404(db, route_id)
    _ensure_route_visibility(actor_user, route)
    return route


def create_route(
    db: Session,
    actor_user: User,
    payload: RouteCreate,
    settings: Settings,
    *,
    request: Request | None = None,
) -> Route:
    _ensure_route_manager(actor_user)
    _ensure_manageable_branch(actor_user, payload.branch_id)

    if db.get(Branch, payload.branch_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Branch not found")

    _ensure_payout_rate_scope(db, payload.payout_rate_id, payload.branch_id)

    route = Route(
        title=payload.title,
        description=payload.description,
        work_date=payload.work_date,
        planned_start_at=payload.planned_start_at,
        planned_end_at=payload.planned_end_at,
        status=RouteStatus.DRAFT,
        branch_id=payload.branch_id,
        promoter_id=None,
        created_by_id=actor_user.id,
        payout_rate_id=payload.payout_rate_id,
    )
    db.add(route)
    db.flush()

    route.points[:] = _build_route_points(route.id, payload.points)
    db.add(route)
    db.flush()

    created_route = get_route_or_404(db, route.id)
    write_audit_log(
        db,
        actor_user=actor_user,
        branch_id=created_route.branch_id,
        entity_type="route",
        entity_id=str(created_route.id),
        action="route.create",
        payload={"after": _serialize_route(created_route, settings)},
        request=request,
    )
    notify_owners_about_key_change(
        db,
        actor_user=actor_user,
        title="Route created",
        body=f"{full_name(actor_user)} created route '{created_route.title}'.",
        payload={"event": "route.create", "route_id": str(created_route.id)},
        branch_id=created_route.branch_id,
        request=request,
    )
    db.commit()
    return get_route_or_404(db, route.id)


def update_route(
    db: Session,
    actor_user: User,
    route: Route,
    payload: RouteUpdate,
    settings: Settings,
    *,
    request: Request | None = None,
) -> Route:
    _ensure_route_manager(actor_user)
    _ensure_manageable_branch(actor_user, route.branch_id)

    if route.status not in {RouteStatus.DRAFT, RouteStatus.ASSIGNED}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only draft or assigned routes can be edited",
        )

    before = _serialize_route(route, settings)
    data = payload.model_dump(exclude_unset=True)

    if "payout_rate_id" in data:
        _ensure_payout_rate_scope(db, data["payout_rate_id"], route.branch_id)

    for field in ("title", "description", "work_date", "planned_start_at", "planned_end_at", "payout_rate_id"):
        if field in data:
            setattr(route, field, data[field])

    if "points" in data and data["points"] is not None:
        _replace_route_points(route, payload.points or [])

    db.add(route)
    db.flush()

    updated_route = get_route_or_404(db, route.id)
    write_audit_log(
        db,
        actor_user=actor_user,
        branch_id=updated_route.branch_id,
        entity_type="route",
        entity_id=str(updated_route.id),
        action="route.update",
        payload={"before": before, "after": _serialize_route(updated_route, settings)},
        request=request,
    )
    notify_owners_about_key_change(
        db,
        actor_user=actor_user,
        title="Route updated",
        body=f"Route '{updated_route.title}' was updated by {full_name(actor_user)}.",
        payload={"event": "route.update", "route_id": str(updated_route.id)},
        branch_id=updated_route.branch_id,
        request=request,
    )
    db.commit()
    return get_route_or_404(db, route.id)


def cancel_route(
    db: Session,
    actor_user: User,
    route: Route,
    settings: Settings,
    *,
    request: Request | None = None,
) -> Route:
    _ensure_route_manager(actor_user)
    _ensure_manageable_branch(actor_user, route.branch_id)

    if route.status not in {RouteStatus.DRAFT, RouteStatus.ASSIGNED}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Route can no longer be cancelled")

    before = _serialize_route(route, settings)
    route.status = RouteStatus.CANCELLED
    route.promoter_id = None
    db.add(route)
    db.flush()

    updated_route = get_route_or_404(db, route.id)
    write_audit_log(
        db,
        actor_user=actor_user,
        branch_id=updated_route.branch_id,
        entity_type="route",
        entity_id=str(updated_route.id),
        action="route.cancel",
        payload={"before": before, "after": _serialize_route(updated_route, settings)},
        request=request,
    )
    db.commit()
    return get_route_or_404(db, route.id)


def assign_route(
    db: Session,
    actor_user: User,
    route: Route,
    payload: RouteAssignRequest,
    settings: Settings,
    *,
    request: Request | None = None,
) -> Route:
    _ensure_route_manager(actor_user)
    _ensure_manageable_branch(actor_user, route.branch_id)

    if route.status in {RouteStatus.IN_PROGRESS, RouteStatus.COMPLETED, RouteStatus.CANCELLED}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Route cannot be assigned anymore")

    promoter = _get_assignable_promoter_or_404(db, payload.promoter_id, route.branch_id)
    before = _serialize_route(route, settings)

    route.promoter_id = promoter.id
    route.status = RouteStatus.ASSIGNED
    db.add(route)
    db.flush()

    updated_route = get_route_or_404(db, route.id)
    write_audit_log(
        db,
        actor_user=actor_user,
        branch_id=updated_route.branch_id,
        entity_type="route",
        entity_id=str(updated_route.id),
        action="route.assign",
        payload={"before": before, "after": _serialize_route(updated_route, settings)},
        request=request,
    )
    notify_route_assignment(
        db,
        route=updated_route,
        promoter=promoter,
        actor_user=actor_user,
        request=request,
    )
    notify_owners_about_key_change(
        db,
        actor_user=actor_user,
        title="Route assigned",
        body=f"Route '{updated_route.title}' was assigned to {full_name(promoter)} by {full_name(actor_user)}.",
        payload={"event": "route.assign", "route_id": str(updated_route.id), "promoter_id": str(promoter.id)},
        branch_id=updated_route.branch_id,
        request=request,
    )
    db.commit()
    return get_route_or_404(db, route.id)


def list_available_promoters(db: Session, actor_user: User) -> list[User]:
    _ensure_route_manager(actor_user)

    stmt = (
        select(User)
        .options(joinedload(User.branch), joinedload(User.role))
        .join(User.role)
        .where(User.status == UserStatus.ACTIVE, User.branch_id.is_not(None))
        .order_by(User.last_name.asc(), User.first_name.asc())
    )

    if is_owner(actor_user):
        stmt = stmt.where(User.role.has(code=RoleCode.PROMOTER.value))
    else:
        stmt = stmt.where(
            User.branch_id == require_branch_assignment(actor_user),
            User.role.has(code=RoleCode.PROMOTER.value),
        )

    return list(db.scalars(stmt))


def start_route(
    db: Session,
    actor_user: User,
    route: Route,
    payload: RouteStartRequest,
    settings: Settings,
    *,
    request: Request | None = None,
) -> PromoterSession:
    _ensure_route_visibility(actor_user, route)

    if get_role_code(actor_user) != RoleCode.PROMOTER or route.promoter_id != actor_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the assigned promoter can start the route")
    if route.status != RouteStatus.ASSIGNED:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Route is not ready to start")
    if _get_route_session(route) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Route session already exists")

    _ensure_coordinate_range(payload.latitude, payload.longitude)

    session = PromoterSession(
        route_id=route.id,
        promoter_id=actor_user.id,
        started_at=payload.captured_at,
        ended_at=None,
        status=PromoterSessionStatus.ACTIVE,
        total_minutes=None,
        leaflet_count=None,
        summary=None,
        started_latitude=payload.latitude,
        started_longitude=payload.longitude,
        finished_latitude=None,
        finished_longitude=None,
    )
    route.status = RouteStatus.IN_PROGRESS
    db.add_all([route, session])
    db.flush()

    geo_ping = GeoPing(
        session_id=session.id,
        route_id=route.id,
        promoter_id=actor_user.id,
        point_id=route.points[0].id if route.points else None,
        captured_at=payload.captured_at,
        latitude=payload.latitude,
        longitude=payload.longitude,
        source=GeoPingSource.START,
        raw_payload={"event": "route.start"},
    )
    db.add(geo_ping)
    db.flush()

    created_session = get_session_or_404(db, session.id)
    updated_route = get_route_or_404(db, route.id)
    write_audit_log(
        db,
        actor_user=actor_user,
        branch_id=updated_route.branch_id,
        entity_type="route",
        entity_id=str(updated_route.id),
        action="route.start",
        payload={
            "route": _serialize_route(updated_route, settings),
            "session": _serialize_session(created_session),
        },
        request=request,
    )
    db.commit()
    return get_session_or_404(db, session.id)


def finish_route(
    db: Session,
    actor_user: User,
    route: Route,
    payload: RouteFinishRequest,
    settings: Settings,
    *,
    request: Request | None = None,
) -> PromoterSession:
    _ensure_route_visibility(actor_user, route)

    if get_role_code(actor_user) != RoleCode.PROMOTER or route.promoter_id != actor_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the assigned promoter can finish the route")
    if route.status != RouteStatus.IN_PROGRESS:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Route is not in progress")

    session = _get_route_session(route)
    if session is None or session.status != PromoterSessionStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Active route session not found")

    if session.started_at is None or payload.captured_at < session.started_at:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Finish time is invalid")

    _ensure_coordinate_range(payload.latitude, payload.longitude)

    if len(session.photo_reports) < 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one photo report is required to finish the route",
        )

    session.ended_at = payload.captured_at
    session.status = PromoterSessionStatus.COMPLETED
    session.leaflet_count = payload.leaflet_count
    session.summary = payload.summary.strip()
    session.finished_latitude = payload.latitude
    session.finished_longitude = payload.longitude
    session.total_minutes = max(0, int((payload.captured_at - session.started_at).total_seconds() // 60))
    route.status = RouteStatus.COMPLETED
    db.add_all([route, session])
    db.flush()

    finish_point_id = route.points[-1].id if route.points else None
    geo_ping = GeoPing(
        session_id=session.id,
        route_id=route.id,
        promoter_id=actor_user.id,
        point_id=finish_point_id,
        captured_at=payload.captured_at,
        latitude=payload.latitude,
        longitude=payload.longitude,
        source=GeoPingSource.FINISH,
        raw_payload={"event": "route.finish"},
    )
    db.add(geo_ping)
    db.flush()

    updated_session = get_session_or_404(db, session.id)
    updated_route = get_route_or_404(db, route.id)
    payout = calculate_payout_for_route(
        db,
        route=updated_route,
        session=updated_session,
        actor_user=actor_user,
        request=request,
    )
    write_audit_log(
        db,
        actor_user=actor_user,
        branch_id=updated_route.branch_id,
        entity_type="route",
        entity_id=str(updated_route.id),
        action="route.finish",
        payload={
            "route": _serialize_route(updated_route, settings),
            "session": _serialize_session(updated_session),
            "payout": to_payout_read(payout).model_dump(mode="json") if payout else None,
        },
        request=request,
    )
    notify_route_completed_to_managers(
        db,
        route=updated_route,
        actor_user=actor_user,
        request=request,
    )
    notify_owners_about_key_change(
        db,
        actor_user=actor_user,
        title="Route completed",
        body=f"Route '{updated_route.title}' was completed by {full_name(actor_user)}.",
        payload={
            "event": "route.finish",
            "route_id": str(updated_route.id),
            "payout_id": str(payout.id) if payout else None,
        },
        branch_id=updated_route.branch_id,
        request=request,
    )
    db.commit()
    return get_session_or_404(db, session.id)


def get_route_session_for_actor(db: Session, actor_user: User, route: Route) -> PromoterSession:
    _ensure_route_visibility(actor_user, route)
    session = _get_route_session(route)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Route session not found")
    return get_session_or_404(db, session.id)


def list_geo_pings_for_actor(db: Session, actor_user: User, session: PromoterSession) -> list[GeoPing]:
    _ensure_session_visibility(actor_user, session)
    return sorted(session.geo_pings, key=lambda item: item.captured_at)


def create_geo_ping(
    db: Session,
    actor_user: User,
    session: PromoterSession,
    payload: GeoPingCreate,
    *,
    request: Request | None = None,
) -> GeoPing:
    _ensure_session_visibility(actor_user, session)

    if get_role_code(actor_user) != RoleCode.PROMOTER or session.promoter_id != actor_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the assigned promoter can send GPS data")
    if session.status != PromoterSessionStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Route session is not active")

    _ensure_coordinate_range(payload.latitude, payload.longitude)

    if payload.point_id is not None:
        point = db.get(RoutePoint, payload.point_id)
        if point is None or point.route_id != session.route_id:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Route point is invalid")

    geo_ping = GeoPing(
        session_id=session.id,
        route_id=session.route_id,
        promoter_id=session.promoter_id,
        point_id=payload.point_id,
        captured_at=payload.captured_at,
        latitude=payload.latitude,
        longitude=payload.longitude,
        accuracy_meters=payload.accuracy_meters,
        speed_mps=payload.speed_mps,
        heading_degrees=payload.heading_degrees,
        source=payload.source,
        raw_payload=payload.raw_payload,
    )
    db.add(geo_ping)
    db.flush()

    created_geo_ping = db.scalar(geo_ping_query().where(GeoPing.id == geo_ping.id))
    if created_geo_ping is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="GPS point was not created")

    write_audit_log(
        db,
        actor_user=actor_user,
        branch_id=session.route.branch_id,
        entity_type="session",
        entity_id=str(session.id),
        action="session.geo_ping.create",
        payload={"geo_ping": to_geo_ping_read(created_geo_ping).model_dump(mode="json")},
        request=request,
    )
    db.commit()
    return created_geo_ping


def _save_upload_file(settings: Settings, route_id: UUID, session_id: UUID, upload: UploadFile) -> str:
    if not upload.filename:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Photo filename is required")

    target_dir = Path(settings.media_root) / "routes" / str(route_id) / str(session_id)
    target_dir.mkdir(parents=True, exist_ok=True)

    safe_name = Path(upload.filename).name.replace(" ", "_")
    relative_path = Path("routes") / str(route_id) / str(session_id) / f"{uuid4().hex}_{safe_name}"
    absolute_path = Path(settings.media_root) / relative_path

    upload.file.seek(0)
    total_written = 0
    with absolute_path.open("wb") as output_file:
        while True:
            chunk = upload.file.read(1024 * 1024)
            if not chunk:
                break
            output_file.write(chunk)
            total_written += len(chunk)

    if total_written == 0:
        absolute_path.unlink(missing_ok=True)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Photo file is empty")

    return relative_path.as_posix()


def upload_photo_report(
    db: Session,
    actor_user: User,
    session: PromoterSession,
    *,
    file: UploadFile,
    captured_at: datetime,
    latitude: float,
    longitude: float,
    point_id: UUID | None,
    notes: str | None,
    settings: Settings,
    request: Request | None = None,
) -> PhotoReport:
    _ensure_session_visibility(actor_user, session)

    if get_role_code(actor_user) != RoleCode.PROMOTER or session.promoter_id != actor_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the assigned promoter can upload photos")
    if session.status != PromoterSessionStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Route session is not active")

    _ensure_coordinate_range(latitude, longitude)

    point = None
    if point_id is not None:
        point = db.get(RoutePoint, point_id)
        if point is None or point.route_id != session.route_id:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Route point is invalid")

    relative_path = _save_upload_file(settings, session.route_id, session.id, file)

    photo_report = PhotoReport(
        route_id=session.route_id,
        session_id=session.id,
        promoter_id=session.promoter_id,
        point_id=point_id,
        reviewed_by_id=None,
        file_path=relative_path,
        thumbnail_path=None,
        captured_at=captured_at,
        latitude=latitude,
        longitude=longitude,
        notes=notes.strip() if notes else None,
        status=PhotoReportStatus.PENDING,
        reviewed_at=None,
    )
    db.add(photo_report)
    db.flush()

    photo_geo_ping = GeoPing(
        session_id=session.id,
        route_id=session.route_id,
        promoter_id=session.promoter_id,
        point_id=point_id,
        captured_at=captured_at,
        latitude=latitude,
        longitude=longitude,
        source=GeoPingSource.PHOTO,
        raw_payload={"event": "photo.upload"},
    )
    db.add(photo_geo_ping)
    db.flush()

    created_photo = get_photo_or_404(db, photo_report.id)
    write_audit_log(
        db,
        actor_user=actor_user,
        branch_id=session.route.branch_id,
        entity_type="photo_report",
        entity_id=str(created_photo.id),
        action="photo_report.create",
        payload={"after": _serialize_photo(created_photo, settings)},
        request=request,
    )
    db.commit()
    return get_photo_or_404(db, photo_report.id)


def list_route_photos_for_actor(db: Session, actor_user: User, route: Route) -> list[PhotoReport]:
    _ensure_route_visibility(actor_user, route)
    return sorted(route.photo_reports, key=lambda item: item.captured_at)


def list_session_photos_for_actor(db: Session, actor_user: User, session: PromoterSession) -> list[PhotoReport]:
    _ensure_session_visibility(actor_user, session)
    return sorted(session.photo_reports, key=lambda item: item.captured_at)


def review_photo_report(
    db: Session,
    actor_user: User,
    photo_report: PhotoReport,
    payload: PhotoReviewRequest,
    settings: Settings,
    *,
    request: Request | None = None,
) -> PhotoReport:
    if not is_route_manager(actor_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    route = photo_report.route
    if route is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Route is not loaded")

    _ensure_manageable_branch(actor_user, route.branch_id)

    before = _serialize_photo(photo_report, settings)
    photo_report.status = payload.status
    photo_report.reviewed_by_id = actor_user.id
    photo_report.reviewed_at = datetime.now(UTC)
    db.add(photo_report)
    db.flush()

    updated_photo = get_photo_or_404(db, photo_report.id)
    write_audit_log(
        db,
        actor_user=actor_user,
        branch_id=route.branch_id,
        entity_type="photo_report",
        entity_id=str(updated_photo.id),
        action="photo_report.review",
        payload={"before": before, "after": _serialize_photo(updated_photo, settings)},
        request=request,
    )
    db.commit()
    return get_photo_or_404(db, photo_report.id)


def get_route_report_for_actor(
    db: Session,
    actor_user: User,
    route: Route,
    settings: Settings,
) -> RouteReportRead:
    _ensure_route_visibility(actor_user, route)

    session = _get_route_session(route)
    if session is None or session.status != PromoterSessionStatus.COMPLETED:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Route report is not available yet")

    photos = sorted(session.photo_reports, key=lambda item: item.captured_at)
    payout = None
    if session.payouts:
        payout = sorted(
            session.payouts,
            key=lambda item: item.calculated_at or item.created_at,
            reverse=True,
        )[0]
    return RouteReportRead(
        route=to_route_read(route, settings),
        session=to_promoter_session_read(session),
        payout=to_payout_read(payout) if payout else None,
        actual_started_at=session.started_at,
        actual_ended_at=session.ended_at,
        total_minutes=session.total_minutes or 0,
        leaflet_count=session.leaflet_count or 0,
        summary=session.summary or "",
        geo_ping_count=len(session.geo_pings),
        photo_count=len(photos),
        photos=[to_photo_report_read(photo, settings) for photo in photos],
    )


def attach_route_map_image(
    db: Session,
    actor_user: User,
    route: Route,
    *,
    file: UploadFile,
    settings: Settings,
    request: Request | None = None,
) -> Route:
    _ensure_route_manager(actor_user)
    _ensure_manageable_branch(actor_user, route.branch_id)

    if not file.filename:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Filename is required")

    target_dir = Path(settings.media_root) / "routes" / str(route.id) / "map"
    target_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(file.filename).name.replace(" ", "_")
    relative_path = Path("routes") / str(route.id) / "map" / f"{uuid4().hex}_{safe_name}"
    absolute_path = Path(settings.media_root) / relative_path

    file.file.seek(0)
    total_written = 0
    with absolute_path.open("wb") as output_file:
        while True:
            chunk = file.file.read(1024 * 1024)
            if not chunk:
                break
            output_file.write(chunk)
            total_written += len(chunk)

    if total_written == 0:
        absolute_path.unlink(missing_ok=True)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Файл пустой")

    before_path = route.map_image_path
    route.map_image_path = relative_path.as_posix()
    db.add(route)
    db.flush()

    updated_route = get_route_or_404(db, route.id)
    write_audit_log(
        db,
        actor_user=actor_user,
        branch_id=updated_route.branch_id,
        entity_type="route",
        entity_id=str(updated_route.id),
        action="route.map_image.attach",
        payload={"before": before_path, "after": route.map_image_path},
        request=request,
    )
    notify_owners_about_key_change(
        db,
        actor_user=actor_user,
        title="Route map updated",
        body=f"Map image was attached to route '{updated_route.title}'.",
        payload={"event": "route.map_image", "route_id": str(updated_route.id)},
        branch_id=updated_route.branch_id,
        request=request,
    )
    db.commit()
    return get_route_or_404(db, route.id)


def accept_promoter_report(
    db: Session,
    actor_user: User,
    session: PromoterSession,
    payload: PromoterReportReviewRequest,
    settings: Settings,
    *,
    request: Request | None = None,
) -> PromoterSession:
    _ensure_session_visibility(actor_user, session)

    if get_role_code(actor_user) not in {RoleCode.AD_DIRECTOR, RoleCode.OWNER}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только директор по рекламе может принять отчёт",
        )

    if session.status != PromoterSessionStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Маршрут ещё не завершён",
        )

    if session.review_status not in {
        PromoterReportReviewStatus.PENDING,
        PromoterReportReviewStatus.REJECTED,
    }:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Отчёт уже был принят",
        )

    session.review_status = PromoterReportReviewStatus.ACCEPTED_BY_DIRECTOR
    session.review_comment = payload.comment
    session.accepted_by_director_id = actor_user.id
    session.accepted_at = datetime.now(UTC)
    db.add(session)
    db.flush()

    updated = get_session_or_404(db, session.id)
    write_audit_log(
        db,
        actor_user=actor_user,
        branch_id=updated.route.branch_id,
        entity_type="promoter_session",
        entity_id=str(updated.id),
        action="promoter_report.accept",
        payload={"session": _serialize_session(updated)},
        request=request,
    )
    notify_owners_about_key_change(
        db,
        actor_user=actor_user,
        title="Promoter report accepted",
        body=(
            f"{full_name(actor_user)} accepted promoter report for route "
            f"'{updated.route.title}'."
        ),
        payload={
            "event": "promoter_report.accept",
            "session_id": str(updated.id),
            "route_id": str(updated.route_id),
        },
        branch_id=updated.route.branch_id,
        request=request,
    )
    db.commit()
    return get_session_or_404(db, session.id)


def reject_promoter_report(
    db: Session,
    actor_user: User,
    session: PromoterSession,
    payload: PromoterReportReviewRequest,
    settings: Settings,
    *,
    request: Request | None = None,
) -> PromoterSession:
    _ensure_session_visibility(actor_user, session)

    if get_role_code(actor_user) not in {RoleCode.AD_DIRECTOR, RoleCode.OWNER}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    if session.status != PromoterSessionStatus.COMPLETED:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Маршрут ещё не завершён")

    session.review_status = PromoterReportReviewStatus.REJECTED
    session.review_comment = payload.comment
    db.add(session)
    db.flush()

    updated = get_session_or_404(db, session.id)
    write_audit_log(
        db,
        actor_user=actor_user,
        branch_id=updated.route.branch_id,
        entity_type="promoter_session",
        entity_id=str(updated.id),
        action="promoter_report.reject",
        payload={"session": _serialize_session(updated), "comment": payload.comment},
        request=request,
    )
    db.commit()
    return get_session_or_404(db, session.id)


def forward_promoter_report(
    db: Session,
    actor_user: User,
    session: PromoterSession,
    payload: PromoterReportReviewRequest,
    settings: Settings,
    *,
    request: Request | None = None,
) -> PromoterSession:
    _ensure_session_visibility(actor_user, session)

    if get_role_code(actor_user) not in {RoleCode.AD_DIRECTOR, RoleCode.OWNER}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    if session.review_status != PromoterReportReviewStatus.ACCEPTED_BY_DIRECTOR:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Сначала отчёт должен быть принят директором по рекламе",
        )

    session.review_status = PromoterReportReviewStatus.FORWARDED_TO_MANAGER
    session.forwarded_by_id = actor_user.id
    session.forwarded_at = datetime.now(UTC)
    if payload.comment:
        session.review_comment = payload.comment
    db.add(session)
    db.flush()

    updated = get_session_or_404(db, session.id)
    write_audit_log(
        db,
        actor_user=actor_user,
        branch_id=updated.route.branch_id,
        entity_type="promoter_session",
        entity_id=str(updated.id),
        action="promoter_report.forward",
        payload={"session": _serialize_session(updated)},
        request=request,
    )
    notify_route_completed_to_managers(
        db,
        route=updated.route,
        actor_user=actor_user,
        request=request,
    )
    notify_owners_about_key_change(
        db,
        actor_user=actor_user,
        title="Promoter report forwarded",
        body=(
            f"{full_name(actor_user)} forwarded promoter report for route "
            f"'{updated.route.title}' to branch manager."
        ),
        payload={
            "event": "promoter_report.forward",
            "session_id": str(updated.id),
            "route_id": str(updated.route_id),
        },
        branch_id=updated.route.branch_id,
        request=request,
    )
    db.commit()
    return get_session_or_404(db, session.id)

