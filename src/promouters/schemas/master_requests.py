from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from promouters.models.enums import AttachmentType, MasterRequestStatus


class MasterRequestCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    address: str | None = Field(default=None, max_length=255)
    client_name: str | None = Field(default=None, max_length=255)
    client_phone: str | None = Field(default=None, max_length=64)
    estimated_amount: Decimal | None = Field(default=None, ge=0, decimal_places=2, max_digits=12)
    currency: str = Field(default="RUB", min_length=3, max_length=3)
    branch_id: UUID
    assignee_id: UUID | None = None
    requested_at: datetime | None = None


class MasterRequestUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    address: str | None = Field(default=None, max_length=255)
    client_name: str | None = Field(default=None, max_length=255)
    client_phone: str | None = Field(default=None, max_length=64)
    estimated_amount: Decimal | None = Field(default=None, ge=0, decimal_places=2, max_digits=12)
    final_amount: Decimal | None = Field(default=None, ge=0, decimal_places=2, max_digits=12)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    assignee_id: UUID | None = None


class MasterRequestStatusChange(BaseModel):
    status: MasterRequestStatus
    note: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    captured_at: datetime | None = None


class MasterRequestCommentCreate(BaseModel):
    body: str = Field(min_length=1)


class MasterRequestCommentRead(BaseModel):
    id: UUID
    master_request_id: UUID
    author_id: UUID
    author_name: str
    body: str
    created_at: datetime


class MasterRequestStatusLogRead(BaseModel):
    id: UUID
    master_request_id: UUID
    changed_by_id: UUID | None
    changed_by_name: str | None
    from_status: str | None
    to_status: str
    note: str | None
    created_at: datetime


class MasterGeoPingRead(BaseModel):
    id: UUID
    master_request_id: UUID
    master_id: UUID
    captured_at: datetime
    latitude: float
    longitude: float
    accuracy_meters: float | None
    status_at_capture: str


class MasterGeoPingCreate(BaseModel):
    captured_at: datetime
    latitude: float
    longitude: float
    accuracy_meters: float | None = None


class BSOAttachmentRead(BaseModel):
    id: UUID
    master_request_id: UUID
    uploaded_by_id: UUID
    uploaded_by_name: str
    attachment_type: str
    file_path: str
    file_url: str
    filename: str
    mime_type: str | None
    size_bytes: int | None
    comment: str | None
    created_at: datetime


class MasterRequestRead(BaseModel):
    id: UUID
    branch_id: UUID
    branch_name: str
    requester_id: UUID
    requester_name: str
    assignee_id: UUID | None
    assignee_name: str | None
    title: str
    description: str | None
    address: str | None
    client_name: str | None
    client_phone: str | None
    estimated_amount: Decimal | None
    final_amount: Decimal | None
    currency: str
    status: str
    geo_tracking_enabled: bool
    requested_at: datetime | None
    accepted_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    handed_over_at: datetime | None
    cancelled_at: datetime | None
    last_known_latitude: float | None
    last_known_longitude: float | None
    last_known_at: datetime | None
    comments: list[MasterRequestCommentRead]
    status_logs: list[MasterRequestStatusLogRead]
    attachments: list[BSOAttachmentRead]
    geo_ping_count: int
    created_at: datetime
    updated_at: datetime


class MasterRequestDeleteResponse(BaseModel):
    id: UUID
    message: str


class BSOAttachmentCreateMeta(BaseModel):
    attachment_type: AttachmentType = AttachmentType.BSO
    comment: str | None = None
