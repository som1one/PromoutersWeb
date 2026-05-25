"""HTTP API для заявок мастера, статусов, БСО и комментариев."""

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile, status
from sqlalchemy.orm import Session

from promouters.api.deps import get_current_user
from promouters.core.config import Settings, get_settings
from promouters.db.session import get_db
from promouters.models.enums import AttachmentType, MasterRequestStatus
from promouters.models.users import User
from promouters.schemas.master_requests import (
    BSOAttachmentRead,
    MasterGeoPingCreate,
    MasterGeoPingRead,
    MasterRequestCommentCreate,
    MasterRequestCommentRead,
    MasterRequestCreate,
    MasterRequestRead,
    MasterRequestStatusChange,
    MasterRequestUpdate,
)
from promouters.services.master_requests import (
    add_master_request_comment,
    change_master_request_status,
    create_master_request,
    get_master_request_for_actor,
    list_master_requests_for_actor,
    report_master_geo_ping,
    to_attachment_read,
    to_comment_read,
    to_geo_ping_read,
    to_master_request_read,
    update_master_request,
    upload_bso_attachment,
)

router = APIRouter(prefix="/master-requests", tags=["master-requests"])


@router.get("", response_model=list[MasterRequestRead])
def get_master_requests(
    request_status: MasterRequestStatus | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> list[MasterRequestRead]:
    return [
        to_master_request_read(item, settings)
        for item in list_master_requests_for_actor(db, current_user, status_filter=request_status)
    ]


@router.post("", response_model=MasterRequestRead, status_code=status.HTTP_201_CREATED)
def create_master_request_endpoint(
    payload: MasterRequestCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> MasterRequestRead:
    created = create_master_request(db, current_user, payload, settings, request=request)
    return to_master_request_read(created, settings)


@router.get("/{master_request_id}", response_model=MasterRequestRead)
def get_master_request(
    master_request_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> MasterRequestRead:
    request_obj = get_master_request_for_actor(db, current_user, master_request_id)
    return to_master_request_read(request_obj, settings)


@router.patch("/{master_request_id}", response_model=MasterRequestRead)
def update_master_request_endpoint(
    master_request_id: UUID,
    payload: MasterRequestUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> MasterRequestRead:
    request_obj = get_master_request_for_actor(db, current_user, master_request_id)
    updated = update_master_request(db, current_user, request_obj, payload, settings, request=request)
    return to_master_request_read(updated, settings)


@router.post("/{master_request_id}/status", response_model=MasterRequestRead)
def change_master_request_status_endpoint(
    master_request_id: UUID,
    payload: MasterRequestStatusChange,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> MasterRequestRead:
    request_obj = get_master_request_for_actor(db, current_user, master_request_id)
    updated = change_master_request_status(db, current_user, request_obj, payload, settings, request=request)
    return to_master_request_read(updated, settings)


@router.post(
    "/{master_request_id}/comments",
    response_model=MasterRequestCommentRead,
    status_code=status.HTTP_201_CREATED,
)
def add_comment_endpoint(
    master_request_id: UUID,
    payload: MasterRequestCommentCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> MasterRequestCommentRead:
    request_obj = get_master_request_for_actor(db, current_user, master_request_id)
    comment = add_master_request_comment(db, current_user, request_obj, payload, settings, request=request)
    return to_comment_read(comment)


@router.post(
    "/{master_request_id}/geo-pings",
    response_model=MasterGeoPingRead,
    status_code=status.HTTP_201_CREATED,
)
def create_master_geo_ping_endpoint(
    master_request_id: UUID,
    payload: MasterGeoPingCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MasterGeoPingRead:
    request_obj = get_master_request_for_actor(db, current_user, master_request_id)
    geo_ping = report_master_geo_ping(db, current_user, request_obj, payload, request=request)
    return to_geo_ping_read(geo_ping)


@router.post(
    "/{master_request_id}/attachments",
    response_model=BSOAttachmentRead,
    status_code=status.HTTP_201_CREATED,
)
def upload_attachment_endpoint(
    master_request_id: UUID,
    request: Request,
    file: UploadFile = File(...),
    attachment_type: AttachmentType = Form(default=AttachmentType.BSO),
    comment: str | None = Form(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> BSOAttachmentRead:
    request_obj = get_master_request_for_actor(db, current_user, master_request_id)
    attachment = upload_bso_attachment(
        db,
        current_user,
        request_obj,
        file=file,
        attachment_type=attachment_type,
        comment=comment,
        settings=settings,
        request=request,
    )
    return to_attachment_read(attachment, settings)
