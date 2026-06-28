from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from promouters.models.enums import (
    GeoPingSource,
    PhotoReportStatus,
    PromoterSessionStatus,
    RoutePointType,
    RouteStatus,
)
from promouters.schemas.finance import PayoutRead


class RoutePointInput(BaseModel):
    sequence: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=255)
    address: str | None = Field(default=None, max_length=255)
    latitude: float | None = None
    longitude: float | None = None
    point_type: RoutePointType = RoutePointType.CHECKPOINT
    planned_arrival_at: datetime | None = None
    notes: str | None = None


class RoutePointRead(BaseModel):
    id: UUID
    route_id: UUID
    sequence: int
    name: str
    address: str | None
    latitude: float | None
    longitude: float | None
    point_type: str
    planned_arrival_at: datetime | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class RouteCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    work_date: date
    planned_start_at: datetime | None = None
    planned_end_at: datetime | None = None
    branch_id: UUID
    payout_rate_id: UUID | None = None
    promoter_id: UUID | None = None
    points: list[RoutePointInput] = Field(min_length=2)


class RouteUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    work_date: date | None = None
    planned_start_at: datetime | None = None
    planned_end_at: datetime | None = None
    payout_rate_id: UUID | None = None
    points: list[RoutePointInput] | None = Field(default=None, min_length=2)


class RouteAssignRequest(BaseModel):
    promoter_id: UUID


class RouteStartRequest(BaseModel):
    captured_at: datetime
    latitude: float
    longitude: float


class RouteFinishRequest(BaseModel):
    captured_at: datetime
    latitude: float
    longitude: float
    leaflet_count: int = Field(ge=0)
    summary: str = Field(min_length=1)

    @field_validator("summary")
    @classmethod
    def strip_summary(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Summary must not be empty")
        return stripped


class PromoterSessionRead(BaseModel):
    id: UUID
    route_id: UUID
    promoter_id: UUID
    promoter_name: str
    status: str
    started_at: datetime | None
    ended_at: datetime | None
    total_minutes: int | None
    leaflet_count: int | None
    summary: str | None
    started_latitude: float | None
    started_longitude: float | None
    finished_latitude: float | None
    finished_longitude: float | None
    photo_count: int
    geo_ping_count: int
    review_status: str = "pending"
    review_comment: str | None = None
    accepted_by_director_id: UUID | None = None
    accepted_by_director_name: str | None = None
    accepted_at: datetime | None = None
    forwarded_by_id: UUID | None = None
    forwarded_by_name: str | None = None
    forwarded_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class PromoterReportReviewRequest(BaseModel):
    comment: str | None = None


class GeoPingCreate(BaseModel):
    captured_at: datetime
    latitude: float
    longitude: float
    accuracy_meters: float | None = None
    speed_mps: float | None = None
    heading_degrees: float | None = None
    source: GeoPingSource = GeoPingSource.TRACKING
    point_id: UUID | None = None
    raw_payload: dict | None = None


class GeoPingRead(BaseModel):
    id: UUID
    session_id: UUID
    route_id: UUID
    promoter_id: UUID
    point_id: UUID | None
    point_name: str | None = None
    captured_at: datetime
    latitude: float
    longitude: float
    accuracy_meters: float | None
    speed_mps: float | None
    heading_degrees: float | None
    source: str


class PhotoReportRead(BaseModel):
    id: UUID
    route_id: UUID
    session_id: UUID
    promoter_id: UUID
    promoter_name: str
    point_id: UUID | None
    point_name: str | None = None
    reviewed_by_id: UUID | None
    reviewed_by_name: str | None = None
    file_path: str
    file_url: str
    thumbnail_path: str | None
    captured_at: datetime
    latitude: float | None
    longitude: float | None
    notes: str | None
    status: str
    reviewed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class PhotoUploadResponse(PhotoReportRead):
    pass


class PhotoReviewRequest(BaseModel):
    status: PhotoReportStatus

    @field_validator("status")
    @classmethod
    def allow_only_review_outcomes(cls, value: PhotoReportStatus) -> PhotoReportStatus:
        if value not in {PhotoReportStatus.ACCEPTED, PhotoReportStatus.REJECTED}:
            raise ValueError("Photo review status must be accepted or rejected")
        return value


class RouteRead(BaseModel):
    id: UUID
    title: str
    description: str | None
    map_image_path: str | None = None
    map_image_url: str | None = None
    work_date: date
    planned_start_at: datetime | None
    planned_end_at: datetime | None
    status: str
    branch_id: UUID
    branch_name: str
    promoter_id: UUID | None
    promoter_name: str | None
    created_by_id: UUID
    created_by_name: str
    payout_rate_id: UUID | None
    current_session: PromoterSessionRead | None
    points: list[RoutePointRead]
    photo_count: int
    geo_ping_count: int
    created_at: datetime
    updated_at: datetime


class RouteReportRead(BaseModel):
    route: RouteRead
    session: PromoterSessionRead
    payout: PayoutRead | None = None
    actual_started_at: datetime | None
    actual_ended_at: datetime | None
    total_minutes: int
    leaflet_count: int
    summary: str
    geo_ping_count: int
    photo_count: int
    photos: list[PhotoReportRead]


class AvailablePromoterRead(BaseModel):
    id: UUID
    full_name: str
    branch_id: UUID | None
    branch_name: str | None = None
    status: str
