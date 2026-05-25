from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from promouters.models.enums import NotificationChannel, NotificationStatus, PromoterSessionStatus, RoleCode
from promouters.models.operations import Notification
from promouters.models.routing import PromoterSession, Route
from promouters.models.users import Role, User
from promouters.schemas.notifications import NotificationRead
from promouters.services.access import get_role_code, is_owner, require_route_manager
from promouters.services.audit import write_audit_log


def _full_name(user: User | None) -> str:
    if user is None:
        return ""
    full_name = " ".join(part for part in [user.first_name, user.last_name] if part).strip()
    return full_name or user.username


def notification_query():
    return select(Notification).options(joinedload(Notification.user))


def to_notification_read(notification: Notification) -> NotificationRead:
    return NotificationRead(
        id=notification.id,
        user_id=notification.user_id,
        title=notification.title,
        body=notification.body,
        channel=notification.channel.value,
        status=notification.status.value,
        payload=notification.payload,
        scheduled_at=notification.scheduled_at,
        sent_at=notification.sent_at,
        read_at=notification.read_at,
        created_at=notification.created_at,
        updated_at=notification.updated_at,
    )


def create_notification(
    db: Session,
    *,
    user: User,
    title: str,
    body: str,
    payload: dict | None = None,
    actor_user: User | None = None,
    branch_id: UUID | None = None,
    request: Request | None = None,
) -> Notification:
    notification = Notification(
        user_id=user.id,
        title=title,
        body=body,
        channel=NotificationChannel.IN_APP,
        status=NotificationStatus.SENT,
        payload=payload,
        scheduled_at=None,
        sent_at=datetime.now(UTC),
        read_at=None,
    )
    db.add(notification)
    db.flush()

    write_audit_log(
        db,
        actor_user=actor_user,
        branch_id=branch_id,
        entity_type="notification",
        entity_id=str(notification.id),
        action="notification.send",
        payload={"after": to_notification_read(notification).model_dump(mode="json")},
        request=request,
    )
    return notification


def list_notifications_for_actor(db: Session, actor_user: User) -> list[Notification]:
    stmt = notification_query().where(Notification.user_id == actor_user.id).order_by(Notification.created_at.desc())
    return list(db.scalars(stmt))


def get_notification_for_actor(db: Session, actor_user: User, notification_id: UUID) -> Notification:
    notification = db.scalar(notification_query().where(Notification.id == notification_id))
    if notification is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    if notification.user_id != actor_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Notification does not belong to you")
    return notification


def mark_notification_read(db: Session, actor_user: User, notification: Notification) -> Notification:
    if notification.user_id != actor_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Notification does not belong to you")
    if notification.read_at is None:
        notification.read_at = datetime.now(UTC)
        notification.status = NotificationStatus.READ
        db.add(notification)
        db.commit()
        db.refresh(notification)
    return notification


def _get_users_by_role_code(
    db: Session,
    *,
    role_code: RoleCode,
    branch_id: UUID | None = None,
) -> list[User]:
    stmt = (
        select(User)
        .join(User.role)
        .options(joinedload(User.role), joinedload(User.branch))
        .where(Role.code == role_code.value)
    )
    if branch_id is not None:
        stmt = stmt.where(User.branch_id == branch_id)
    return list(db.scalars(stmt))


def notify_route_assignment(
    db: Session,
    *,
    route: Route,
    promoter: User,
    actor_user: User | None,
    request: Request | None = None,
) -> Notification:
    title = "New route assigned"
    body = f"You have been assigned to route '{route.title}' on {route.work_date.isoformat()}."
    return create_notification(
        db,
        user=promoter,
        title=title,
        body=body,
        payload={"event": "route.assign", "route_id": str(route.id)},
        actor_user=actor_user,
        branch_id=route.branch_id,
        request=request,
    )


def notify_route_completed_to_managers(
    db: Session,
    *,
    route: Route,
    actor_user: User | None,
    request: Request | None = None,
) -> list[Notification]:
    managers = _get_users_by_role_code(db, role_code=RoleCode.BRANCH_MANAGER, branch_id=route.branch_id)
    notifications: list[Notification] = []
    for manager in managers:
        notifications.append(
            create_notification(
                db,
                user=manager,
                title="Route completed",
                body=f"Route '{route.title}' has been completed by {_full_name(route.promoter)}.",
                payload={"event": "route.finish", "route_id": str(route.id)},
                actor_user=actor_user,
                branch_id=route.branch_id,
                request=request,
            )
        )
    return notifications


def notify_owners_about_key_change(
    db: Session,
    *,
    actor_user: User | None,
    title: str,
    body: str,
    payload: dict | None,
    branch_id: UUID | None,
    request: Request | None = None,
) -> list[Notification]:
    owners = _get_users_by_role_code(db, role_code=RoleCode.OWNER)
    notifications: list[Notification] = []
    for owner in owners:
        notifications.append(
            create_notification(
                db,
                user=owner,
                title=title,
                body=body,
                payload=payload,
                actor_user=actor_user,
                branch_id=branch_id,
                request=request,
            )
        )
    return notifications


def dispatch_photo_report_reminders(
    db: Session,
    actor_user: User,
    *,
    reminder_interval_minutes: int,
    request: Request | None = None,
) -> list[Notification]:
    require_route_manager(actor_user)
    threshold = datetime.now(UTC) - timedelta(minutes=reminder_interval_minutes)

    stmt = (
        select(PromoterSession)
        .options(
            joinedload(PromoterSession.route).joinedload(Route.promoter),
            joinedload(PromoterSession.promoter),
            joinedload(PromoterSession.photo_reports),
        )
        .where(PromoterSession.status == PromoterSessionStatus.ACTIVE)
    )
    if not is_owner(actor_user):
        stmt = stmt.join(PromoterSession.route).where(Route.branch_id == actor_user.branch_id)

    notifications: list[Notification] = []
    for session in db.scalars(stmt):
        promoter = session.promoter
        route = session.route
        if promoter is None or route is None:
            continue

        latest_photo_time = max((photo.captured_at for photo in session.photo_reports), default=session.started_at)
        if latest_photo_time is None or latest_photo_time > threshold:
            continue

        notification = create_notification(
            db,
            user=promoter,
            title="Photo report reminder",
            body=f"Please upload a photo report for route '{route.title}'.",
            payload={
                "event": "photo_report.reminder",
                "route_id": str(route.id),
                "session_id": str(session.id),
            },
            actor_user=actor_user,
            branch_id=route.branch_id,
            request=request,
        )
        notifications.append(notification)

    db.commit()
    return notifications
