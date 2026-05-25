from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile, status
from sqlalchemy.orm import Session

from promouters.api.deps import get_current_user
from promouters.core.config import Settings, get_settings
from promouters.db.session import get_db
from promouters.models.enums import RouteStatus
from promouters.models.users import User
from promouters.schemas.routes import (
    AvailablePromoterRead,
    GeoPingCreate,
    GeoPingRead,
    PhotoReportRead,
    PhotoReviewRequest,
    PhotoUploadResponse,
    PromoterReportReviewRequest,
    PromoterSessionRead,
    RouteAssignRequest,
    RouteCreate,
    RouteFinishRequest,
    RouteRead,
    RouteReportRead,
    RouteStartRequest,
    RouteUpdate,
)
from promouters.services.routes import (
    accept_promoter_report,
    assign_route,
    attach_route_map_image,
    cancel_route,
    create_geo_ping,
    create_route,
    finish_route,
    forward_promoter_report,
    get_photo_or_404,
    get_route_for_actor,
    get_route_report_for_actor,
    get_route_session_for_actor,
    get_session_or_404,
    list_available_promoters,
    list_geo_pings_for_actor,
    list_route_photos_for_actor,
    list_routes_for_actor,
    list_session_photos_for_actor,
    reject_promoter_report,
    review_photo_report,
    start_route,
    to_available_promoter_read,
    to_geo_ping_read,
    to_photo_report_read,
    to_promoter_session_read,
    to_route_read,
    update_route,
    upload_photo_report,
)

router = APIRouter(tags=["routes"])


@router.get("/routes", response_model=list[RouteRead])
def get_routes(
    route_status: RouteStatus | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> list[RouteRead]:
    return [
        to_route_read(route, settings)
        for route in list_routes_for_actor(db, current_user, route_status=route_status)
    ]


@router.get("/routes/available-promoters", response_model=list[AvailablePromoterRead])
def get_available_promoters(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[AvailablePromoterRead]:
    return [to_available_promoter_read(user) for user in list_available_promoters(db, current_user)]


@router.post("/routes", response_model=RouteRead, status_code=status.HTTP_201_CREATED)
def create_route_endpoint(
    payload: RouteCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> RouteRead:
    return to_route_read(create_route(db, current_user, payload, settings, request=request), settings)


@router.get("/routes/{route_id}", response_model=RouteRead)
def get_route(
    route_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> RouteRead:
    return to_route_read(get_route_for_actor(db, current_user, route_id), settings)


@router.patch("/routes/{route_id}", response_model=RouteRead)
def update_route_endpoint(
    route_id: UUID,
    payload: RouteUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> RouteRead:
    route = get_route_for_actor(db, current_user, route_id)
    updated_route = update_route(db, current_user, route, payload, settings, request=request)
    return to_route_read(updated_route, settings)


@router.post("/routes/{route_id}/assign", response_model=RouteRead)
def assign_route_endpoint(
    route_id: UUID,
    payload: RouteAssignRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> RouteRead:
    route = get_route_for_actor(db, current_user, route_id)
    updated_route = assign_route(db, current_user, route, payload, settings, request=request)
    return to_route_read(updated_route, settings)


@router.post("/routes/{route_id}/cancel", response_model=RouteRead)
def cancel_route_endpoint(
    route_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> RouteRead:
    route = get_route_for_actor(db, current_user, route_id)
    updated_route = cancel_route(db, current_user, route, settings, request=request)
    return to_route_read(updated_route, settings)


@router.post("/routes/{route_id}/start", response_model=PromoterSessionRead)
def start_route_endpoint(
    route_id: UUID,
    payload: RouteStartRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> PromoterSessionRead:
    route = get_route_for_actor(db, current_user, route_id)
    session = start_route(db, current_user, route, payload, settings, request=request)
    return to_promoter_session_read(session)


@router.post("/routes/{route_id}/finish", response_model=PromoterSessionRead)
def finish_route_endpoint(
    route_id: UUID,
    payload: RouteFinishRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> PromoterSessionRead:
    route = get_route_for_actor(db, current_user, route_id)
    session = finish_route(db, current_user, route, payload, settings, request=request)
    return to_promoter_session_read(session)


@router.get("/routes/{route_id}/session", response_model=PromoterSessionRead)
def get_route_session(
    route_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PromoterSessionRead:
    route = get_route_for_actor(db, current_user, route_id)
    session = get_route_session_for_actor(db, current_user, route)
    return to_promoter_session_read(session)


@router.get("/routes/{route_id}/photos", response_model=list[PhotoReportRead])
def get_route_photos(
    route_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> list[PhotoReportRead]:
    route = get_route_for_actor(db, current_user, route_id)
    return [to_photo_report_read(photo, settings) for photo in list_route_photos_for_actor(db, current_user, route)]


@router.get("/routes/{route_id}/report", response_model=RouteReportRead)
def get_route_report(
    route_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> RouteReportRead:
    route = get_route_for_actor(db, current_user, route_id)
    return get_route_report_for_actor(db, current_user, route, settings)


@router.get("/sessions/{session_id}/geo-pings", response_model=list[GeoPingRead])
def get_session_geo_pings(
    session_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[GeoPingRead]:
    session = get_session_or_404(db, session_id)
    return [to_geo_ping_read(geo_ping) for geo_ping in list_geo_pings_for_actor(db, current_user, session)]


@router.post("/sessions/{session_id}/geo-pings", response_model=GeoPingRead, status_code=status.HTTP_201_CREATED)
def create_geo_ping_endpoint(
    session_id: UUID,
    payload: GeoPingCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> GeoPingRead:
    session = get_session_or_404(db, session_id)
    geo_ping = create_geo_ping(db, current_user, session, payload, request=request)
    return to_geo_ping_read(geo_ping)


@router.get("/sessions/{session_id}/photos", response_model=list[PhotoReportRead])
def get_session_photos(
    session_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> list[PhotoReportRead]:
    session = get_session_or_404(db, session_id)
    return [
        to_photo_report_read(photo, settings)
        for photo in list_session_photos_for_actor(db, current_user, session)
    ]


@router.post("/sessions/{session_id}/photos", response_model=PhotoUploadResponse, status_code=status.HTTP_201_CREATED)
def upload_photo_endpoint(
    session_id: UUID,
    request: Request,
    file: UploadFile = File(...),
    captured_at: datetime = Form(...),
    latitude: float = Form(...),
    longitude: float = Form(...),
    point_id: UUID | None = Form(default=None),
    notes: str | None = Form(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> PhotoUploadResponse:
    session = get_session_or_404(db, session_id)
    photo = upload_photo_report(
        db,
        current_user,
        session,
        file=file,
        captured_at=captured_at,
        latitude=latitude,
        longitude=longitude,
        point_id=point_id,
        notes=notes,
        settings=settings,
        request=request,
    )
    return to_photo_report_read(photo, settings)


@router.post("/photo-reports/{photo_id}/review", response_model=PhotoReportRead)
def review_photo_endpoint(
    photo_id: UUID,
    payload: PhotoReviewRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> PhotoReportRead:
    photo_report = get_photo_or_404(db, photo_id)
    updated_photo = review_photo_report(db, current_user, photo_report, payload, settings, request=request)
    return to_photo_report_read(updated_photo, settings)


@router.post("/routes/{route_id}/map-image", response_model=RouteRead)
def attach_route_map_endpoint(
    route_id: UUID,
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> RouteRead:
    route = get_route_for_actor(db, current_user, route_id)
    updated = attach_route_map_image(db, current_user, route, file=file, settings=settings, request=request)
    return to_route_read(updated, settings)


@router.post("/sessions/{session_id}/accept-report", response_model=PromoterSessionRead)
def accept_promoter_report_endpoint(
    session_id: UUID,
    payload: PromoterReportReviewRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> PromoterSessionRead:
    session = get_session_or_404(db, session_id)
    updated = accept_promoter_report(db, current_user, session, payload, settings, request=request)
    return to_promoter_session_read(updated)


@router.post("/sessions/{session_id}/reject-report", response_model=PromoterSessionRead)
def reject_promoter_report_endpoint(
    session_id: UUID,
    payload: PromoterReportReviewRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> PromoterSessionRead:
    session = get_session_or_404(db, session_id)
    updated = reject_promoter_report(db, current_user, session, payload, settings, request=request)
    return to_promoter_session_read(updated)


@router.post("/sessions/{session_id}/forward-report", response_model=PromoterSessionRead)
def forward_promoter_report_endpoint(
    session_id: UUID,
    payload: PromoterReportReviewRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> PromoterSessionRead:
    session = get_session_or_404(db, session_id)
    updated = forward_promoter_report(db, current_user, session, payload, settings, request=request)
    return to_promoter_session_read(updated)
