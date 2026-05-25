"""Notifications inbox (any authenticated user)."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from promouters.db.session import get_db
from promouters.models.enums import NotificationStatus
from promouters.models.operations import Notification
from promouters.models.users import User
from promouters.web.deps import get_web_user, render


router = APIRouter()


@router.get("/")
async def notifications_list(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_web_user),
):
    rows = list(
        db.scalars(
            select(Notification)
            .where(Notification.user_id == user.id)
            .order_by(Notification.created_at.desc())
            .limit(200)
        )
    )
    return render(
        request,
        "notifications.html",
        user=user,
        active_page="notifications",
        notifications=rows,
    )


@router.post("/{notification_id}/read")
async def notification_mark_read(
    notification_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_web_user),
):
    try:
        target_id = UUID(notification_id)
    except ValueError:
        return RedirectResponse("/admin/notifications", status_code=302)

    n = db.scalar(
        select(Notification).where(
            Notification.id == target_id,
            Notification.user_id == user.id,
        )
    )
    if n and n.status != NotificationStatus.READ:
        n.status = NotificationStatus.READ
        n.read_at = datetime.utcnow()
        db.commit()
    return RedirectResponse("/admin/notifications?updated=1", status_code=302)
