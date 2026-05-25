from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from promouters.api.deps import get_current_user
from promouters.core.config import Settings, get_settings
from promouters.db.session import get_db
from promouters.models.users import User
from promouters.schemas.notifications import (
    NotificationMarkReadResponse,
    NotificationRead,
    PhotoReminderDispatchResponse,
)
from promouters.services.notifications import (
    dispatch_photo_report_reminders,
    get_notification_for_actor,
    list_notifications_for_actor,
    mark_notification_read,
    to_notification_read,
)

router = APIRouter(tags=["notifications"])


@router.get("/notifications", response_model=list[NotificationRead])
def get_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[NotificationRead]:
    return [to_notification_read(item) for item in list_notifications_for_actor(db, current_user)]


@router.post("/notifications/{notification_id}/read", response_model=NotificationMarkReadResponse)
def mark_notification_read_endpoint(
    notification_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NotificationMarkReadResponse:
    notification = get_notification_for_actor(db, current_user, notification_id)
    updated = mark_notification_read(db, current_user, notification)
    return NotificationMarkReadResponse(success=True, notification=to_notification_read(updated))


@router.post("/notifications/photo-reminders/dispatch", response_model=PhotoReminderDispatchResponse)
def dispatch_photo_reminders_endpoint(
    request: Request,
    reminder_interval_minutes: int | None = Query(default=None, ge=1, le=240),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> PhotoReminderDispatchResponse:
    notifications = dispatch_photo_report_reminders(
        db,
        current_user,
        reminder_interval_minutes=reminder_interval_minutes or settings.photo_report_reminder_minutes,
        request=request,
    )
    return PhotoReminderDispatchResponse(
        created_count=len(notifications),
        notification_ids=[notification.id for notification in notifications],
    )
