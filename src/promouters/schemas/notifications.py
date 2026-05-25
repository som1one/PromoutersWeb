from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class NotificationRead(BaseModel):
    id: UUID
    user_id: UUID
    title: str
    body: str
    channel: str
    status: str
    payload: dict | None
    scheduled_at: datetime | None
    sent_at: datetime | None
    read_at: datetime | None
    created_at: datetime
    updated_at: datetime


class NotificationMarkReadResponse(BaseModel):
    success: bool
    notification: NotificationRead


class PhotoReminderDispatchResponse(BaseModel):
    created_count: int
    notification_ids: list[UUID]
