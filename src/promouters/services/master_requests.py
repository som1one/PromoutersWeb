"""Сервис мастер-контура: заявки, статусы, БСО, комментарии, гео мастера."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import HTTPException, Request, UploadFile, status
from sqlalchemy import Select, select
from sqlalchemy.orm import Session, joinedload, selectinload

from promouters.core.config import Settings
from promouters.models.enums import (
    GEO_TRACKED_MASTER_STATUSES,
    AttachmentType,
    MasterRequestStatus,
    RoleCode,
)
from promouters.models.operations import (
    BSOAttachment,
    MasterGeoPing,
    MasterRequest,
    MasterRequestComment,
    MasterRequestStatusLog,
)
from promouters.models.users import Branch, User
from promouters.schemas.master_requests import (
    BSOAttachmentRead,
    MasterGeoPingCreate,
    MasterGeoPingRead,
    MasterRequestCommentCreate,
    MasterRequestCommentRead,
    MasterRequestCreate,
    MasterRequestRead,
    MasterRequestStatusChange,
    MasterRequestStatusLogRead,
    MasterRequestUpdate,
)
from promouters.services.access import (
    ensure_same_branch,
    get_role_code,
    is_owner,
    require_branch_assignment,
)
from promouters.services.audit import write_audit_log
from promouters.services.notifications import notify_owners_about_key_change


# Допустимые переходы статусов согласно ТЗ
ALLOWED_STATUS_TRANSITIONS: dict[MasterRequestStatus, set[MasterRequestStatus]] = {
    MasterRequestStatus.NEW: {MasterRequestStatus.ACCEPTED, MasterRequestStatus.HANDED_OVER, MasterRequestStatus.CANCELLED},
    MasterRequestStatus.ACCEPTED: {
        MasterRequestStatus.ON_THE_WAY,
        MasterRequestStatus.HANDED_OVER,
        MasterRequestStatus.CANCELLED,
    },
    MasterRequestStatus.ON_THE_WAY: {
        MasterRequestStatus.IN_PROGRESS,
        MasterRequestStatus.HANDED_OVER,
        MasterRequestStatus.CANCELLED,
    },
    MasterRequestStatus.IN_PROGRESS: {
        MasterRequestStatus.COMPLETED,
        MasterRequestStatus.HANDED_OVER,
        MasterRequestStatus.CANCELLED,
    },
    MasterRequestStatus.COMPLETED: {MasterRequestStatus.HANDED_OVER},
    MasterRequestStatus.HANDED_OVER: set(),
    MasterRequestStatus.CANCELLED: set(),
}


def _full_name(user: User | None) -> str:
    if user is None:
        return ""
    full_name = " ".join(part for part in [user.first_name, user.last_name] if part).strip()
    return full_name or user.username


def _as_float(value: Decimal | float | None) -> float | None:
    if value is None:
        return None
    return float(value)


def _media_url(settings: Settings, relative_path: str) -> str:
    base_url = settings.media_url.rstrip("/")
    return f"{base_url}/{relative_path.replace(chr(92), '/')}"


def master_request_query() -> Select[tuple[MasterRequest]]:
    return (
        select(MasterRequest)
        .options(
            joinedload(MasterRequest.branch),
            joinedload(MasterRequest.requester),
            joinedload(MasterRequest.assignee),
            selectinload(MasterRequest.comments).joinedload(MasterRequestComment.author),
            selectinload(MasterRequest.status_logs).joinedload(MasterRequestStatusLog.changed_by),
            selectinload(MasterRequest.attachments).joinedload(BSOAttachment.uploaded_by),
            selectinload(MasterRequest.geo_pings),
        )
    )


def to_comment_read(comment: MasterRequestComment) -> MasterRequestCommentRead:
    return MasterRequestCommentRead(
        id=comment.id,
        master_request_id=comment.master_request_id,
        author_id=comment.author_id,
        author_name=_full_name(comment.author),
        body=comment.body,
        created_at=comment.created_at,
    )


def to_status_log_read(log: MasterRequestStatusLog) -> MasterRequestStatusLogRead:
    return MasterRequestStatusLogRead(
        id=log.id,
        master_request_id=log.master_request_id,
        changed_by_id=log.changed_by_id,
        changed_by_name=_full_name(log.changed_by) if log.changed_by else None,
        from_status=log.from_status.value if log.from_status else None,
        to_status=log.to_status.value,
        note=log.note,
        created_at=log.created_at,
    )


def to_geo_ping_read(geo: MasterGeoPing) -> MasterGeoPingRead:
    return MasterGeoPingRead(
        id=geo.id,
        master_request_id=geo.master_request_id,
        master_id=geo.master_id,
        captured_at=geo.captured_at,
        latitude=_as_float(geo.latitude) or 0.0,
        longitude=_as_float(geo.longitude) or 0.0,
        accuracy_meters=_as_float(geo.accuracy_meters),
        status_at_capture=geo.status_at_capture.value,
    )


def to_attachment_read(attachment: BSOAttachment, settings: Settings) -> BSOAttachmentRead:
    return BSOAttachmentRead(
        id=attachment.id,
        master_request_id=attachment.master_request_id,
        uploaded_by_id=attachment.uploaded_by_id,
        uploaded_by_name=_full_name(attachment.uploaded_by),
        attachment_type=attachment.attachment_type.value,
        file_path=attachment.file_path,
        file_url=_media_url(settings, attachment.file_path),
        filename=attachment.filename,
        mime_type=attachment.mime_type,
        size_bytes=attachment.size_bytes,
        comment=attachment.comment,
        created_at=attachment.created_at,
    )


def to_master_request_read(request_obj: MasterRequest, settings: Settings) -> MasterRequestRead:
    return MasterRequestRead(
        id=request_obj.id,
        branch_id=request_obj.branch_id,
        branch_name=request_obj.branch.name if request_obj.branch else "",
        requester_id=request_obj.requester_id,
        requester_name=_full_name(request_obj.requester),
        assignee_id=request_obj.assignee_id,
        assignee_name=_full_name(request_obj.assignee) if request_obj.assignee else None,
        title=request_obj.title,
        description=request_obj.description,
        address=request_obj.address,
        client_name=request_obj.client_name,
        client_phone=request_obj.client_phone,
        estimated_amount=request_obj.estimated_amount,
        final_amount=request_obj.final_amount,
        currency=request_obj.currency,
        status=request_obj.status.value,
        geo_tracking_enabled=request_obj.geo_tracking_enabled,
        requested_at=request_obj.requested_at,
        accepted_at=request_obj.accepted_at,
        started_at=request_obj.started_at,
        completed_at=request_obj.completed_at,
        handed_over_at=request_obj.handed_over_at,
        cancelled_at=request_obj.cancelled_at,
        last_known_latitude=_as_float(request_obj.last_known_latitude),
        last_known_longitude=_as_float(request_obj.last_known_longitude),
        last_known_at=request_obj.last_known_at,
        comments=[to_comment_read(comment) for comment in request_obj.comments],
        status_logs=[to_status_log_read(log) for log in request_obj.status_logs],
        attachments=[to_attachment_read(attachment, settings) for attachment in request_obj.attachments],
        geo_ping_count=len(request_obj.geo_pings),
        created_at=request_obj.created_at,
        updated_at=request_obj.updated_at,
    )


def get_master_request_or_404(db: Session, master_request_id: UUID) -> MasterRequest:
    request_obj = db.scalar(master_request_query().where(MasterRequest.id == master_request_id))
    if request_obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Master request not found"
        )
    return request_obj


def _ensure_can_view(actor_user: User, request_obj: MasterRequest) -> None:
    role_code = get_role_code(actor_user)
    if role_code == RoleCode.OWNER:
        return
    ensure_same_branch(actor_user, request_obj.branch_id)
    if role_code == RoleCode.MASTER and request_obj.assignee_id != actor_user.id and request_obj.requester_id != actor_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")


def _ensure_can_create(actor_user: User, branch_id: UUID) -> None:
    role_code = get_role_code(actor_user)
    if role_code not in {RoleCode.OWNER, RoleCode.BRANCH_MANAGER, RoleCode.AD_DIRECTOR}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only managers can create master requests")
    if not is_owner(actor_user):
        ensure_same_branch(actor_user, branch_id)


def _ensure_can_edit(actor_user: User, request_obj: MasterRequest) -> None:
    role_code = get_role_code(actor_user)
    if role_code == RoleCode.OWNER:
        return
    if role_code in {RoleCode.BRANCH_MANAGER, RoleCode.AD_DIRECTOR}:
        ensure_same_branch(actor_user, request_obj.branch_id)
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")


def _ensure_can_change_status(actor_user: User, request_obj: MasterRequest) -> None:
    role_code = get_role_code(actor_user)
    if role_code == RoleCode.OWNER:
        return
    ensure_same_branch(actor_user, request_obj.branch_id)
    if role_code == RoleCode.MASTER:
        if request_obj.assignee_id != actor_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Master is not assigned to this request")
        return
    if role_code in {RoleCode.BRANCH_MANAGER, RoleCode.AD_DIRECTOR, RoleCode.DISPATCHER}:
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")


def _ensure_can_comment(actor_user: User, request_obj: MasterRequest) -> None:
    _ensure_can_view(actor_user, request_obj)


def _validate_assignee(db: Session, branch_id: UUID, assignee_id: UUID | None) -> User | None:
    if assignee_id is None:
        return None
    assignee = db.scalar(
        select(User).options(joinedload(User.role)).where(User.id == assignee_id)
    )
    if assignee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignee not found")
    if assignee.branch_id != branch_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Assignee belongs to another branch",
        )
    if assignee.role is None or RoleCode(assignee.role.code) != RoleCode.MASTER:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Assignee must be a master",
        )
    return assignee


def list_master_requests_for_actor(
    db: Session,
    actor_user: User,
    *,
    status_filter: MasterRequestStatus | None = None,
) -> list[MasterRequest]:
    stmt = master_request_query().order_by(MasterRequest.created_at.desc())
    role_code = get_role_code(actor_user)

    if role_code == RoleCode.OWNER:
        pass
    elif role_code in {RoleCode.BRANCH_MANAGER, RoleCode.AD_DIRECTOR}:
        stmt = stmt.where(MasterRequest.branch_id == require_branch_assignment(actor_user))
    elif role_code == RoleCode.MASTER:
        actor_branch_id = require_branch_assignment(actor_user)
        stmt = stmt.where(
            MasterRequest.branch_id == actor_branch_id,
            (MasterRequest.assignee_id == actor_user.id) | (MasterRequest.assignee_id.is_(None)),
        )
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    if status_filter is not None:
        stmt = stmt.where(MasterRequest.status == status_filter)

    return list(db.scalars(stmt))


def get_master_request_for_actor(db: Session, actor_user: User, master_request_id: UUID) -> MasterRequest:
    request_obj = get_master_request_or_404(db, master_request_id)
    _ensure_can_view(actor_user, request_obj)
    return request_obj


def create_master_request(
    db: Session,
    actor_user: User,
    payload: MasterRequestCreate,
    settings: Settings,
    *,
    request: Request | None = None,
) -> MasterRequest:
    _ensure_can_create(actor_user, payload.branch_id)
    if db.get(Branch, payload.branch_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Branch not found")

    _validate_assignee(db, payload.branch_id, payload.assignee_id)

    request_obj = MasterRequest(
        branch_id=payload.branch_id,
        requester_id=actor_user.id,
        assignee_id=payload.assignee_id,
        title=payload.title,
        description=payload.description,
        address=payload.address,
        client_name=payload.client_name,
        client_phone=payload.client_phone,
        estimated_amount=payload.estimated_amount,
        currency=payload.currency.upper(),
        status=MasterRequestStatus.NEW,
        geo_tracking_enabled=False,
        requested_at=payload.requested_at or datetime.now(UTC),
    )
    db.add(request_obj)
    db.flush()

    status_log = MasterRequestStatusLog(
        master_request_id=request_obj.id,
        changed_by_id=actor_user.id,
        from_status=None,
        to_status=MasterRequestStatus.NEW,
        note="Заявка создана",
        created_at=datetime.now(UTC),
    )
    db.add(status_log)
    db.flush()

    created = get_master_request_or_404(db, request_obj.id)
    write_audit_log(
        db,
        actor_user=actor_user,
        branch_id=created.branch_id,
        entity_type="master_request",
        entity_id=str(created.id),
        action="master_request.create",
        payload={"after": to_master_request_read(created, settings).model_dump(mode="json")},
        request=request,
    )
    notify_owners_about_key_change(
        db,
        actor_user=actor_user,
        title="Master request created",
        body=f"{_full_name(actor_user)} created master request '{created.title}'.",
        payload={"event": "master_request.create", "master_request_id": str(created.id)},
        branch_id=created.branch_id,
        request=request,
    )
    db.commit()
    return get_master_request_or_404(db, request_obj.id)


def update_master_request(
    db: Session,
    actor_user: User,
    request_obj: MasterRequest,
    payload: MasterRequestUpdate,
    settings: Settings,
    *,
    request: Request | None = None,
) -> MasterRequest:
    _ensure_can_edit(actor_user, request_obj)

    if request_obj.status in {MasterRequestStatus.HANDED_OVER, MasterRequestStatus.CANCELLED}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Master request can no longer be edited",
        )

    before = to_master_request_read(request_obj, settings).model_dump(mode="json")
    data = payload.model_dump(exclude_unset=True)

    if "assignee_id" in data:
        _validate_assignee(db, request_obj.branch_id, data["assignee_id"])
        request_obj.assignee_id = data["assignee_id"]

    for field in (
        "title",
        "description",
        "address",
        "client_name",
        "client_phone",
        "estimated_amount",
        "final_amount",
    ):
        if field in data:
            setattr(request_obj, field, data[field])

    if "currency" in data and data["currency"] is not None:
        request_obj.currency = data["currency"].upper()

    db.add(request_obj)
    db.flush()

    updated = get_master_request_or_404(db, request_obj.id)
    write_audit_log(
        db,
        actor_user=actor_user,
        branch_id=updated.branch_id,
        entity_type="master_request",
        entity_id=str(updated.id),
        action="master_request.update",
        payload={"before": before, "after": to_master_request_read(updated, settings).model_dump(mode="json")},
        request=request,
    )
    notify_owners_about_key_change(
        db,
        actor_user=actor_user,
        title="Master request updated",
        body=f"Master request '{updated.title}' was updated by {_full_name(actor_user)}.",
        payload={"event": "master_request.update", "master_request_id": str(updated.id)},
        branch_id=updated.branch_id,
        request=request,
    )
    db.commit()
    return get_master_request_or_404(db, request_obj.id)


def change_master_request_status(
    db: Session,
    actor_user: User,
    request_obj: MasterRequest,
    payload: MasterRequestStatusChange,
    settings: Settings,
    *,
    request: Request | None = None,
) -> MasterRequest:
    _ensure_can_change_status(actor_user, request_obj)

    target_status = payload.status
    current_status = request_obj.status

    if target_status not in ALLOWED_STATUS_TRANSITIONS.get(current_status, set()):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Status transition {current_status.value} -> {target_status.value} is not allowed",
        )

    role_code = get_role_code(actor_user)
    if role_code == RoleCode.MASTER and target_status not in {
        MasterRequestStatus.ACCEPTED,
        MasterRequestStatus.ON_THE_WAY,
        MasterRequestStatus.IN_PROGRESS,
        MasterRequestStatus.COMPLETED,
        MasterRequestStatus.HANDED_OVER,
    }:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Master cannot perform this status transition",
        )

    now = datetime.now(UTC)
    captured_at = payload.captured_at or now

    before = to_master_request_read(request_obj, settings).model_dump(mode="json")
    request_obj.status = target_status

    if target_status == MasterRequestStatus.ACCEPTED:
        request_obj.accepted_at = now
    elif target_status == MasterRequestStatus.ON_THE_WAY:
        request_obj.started_at = request_obj.started_at or now
    elif target_status == MasterRequestStatus.COMPLETED:
        request_obj.completed_at = now
    elif target_status == MasterRequestStatus.HANDED_OVER:
        request_obj.handed_over_at = now
    elif target_status == MasterRequestStatus.CANCELLED:
        request_obj.cancelled_at = now

    # Авто-вкл/выкл геопозиции по требованиям ТЗ
    request_obj.geo_tracking_enabled = target_status in GEO_TRACKED_MASTER_STATUSES

    if request_obj.geo_tracking_enabled and payload.latitude is not None and payload.longitude is not None:
        if not (-90 <= payload.latitude <= 90) or not (-180 <= payload.longitude <= 180):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Geo coordinates are out of range",
            )
        request_obj.last_known_latitude = payload.latitude
        request_obj.last_known_longitude = payload.longitude
        request_obj.last_known_at = captured_at

        if request_obj.assignee_id is not None:
            geo_ping = MasterGeoPing(
                master_request_id=request_obj.id,
                master_id=request_obj.assignee_id,
                captured_at=captured_at,
                latitude=payload.latitude,
                longitude=payload.longitude,
                status_at_capture=target_status,
            )
            db.add(geo_ping)

    status_log = MasterRequestStatusLog(
        master_request_id=request_obj.id,
        changed_by_id=actor_user.id,
        from_status=current_status,
        to_status=target_status,
        note=payload.note,
        created_at=now,
    )
    db.add(status_log)
    db.add(request_obj)
    db.flush()

    updated = get_master_request_or_404(db, request_obj.id)
    write_audit_log(
        db,
        actor_user=actor_user,
        branch_id=updated.branch_id,
        entity_type="master_request",
        entity_id=str(updated.id),
        action=f"master_request.status.{target_status.value}",
        payload={"before": before, "after": to_master_request_read(updated, settings).model_dump(mode="json")},
        request=request,
    )
    notify_owners_about_key_change(
        db,
        actor_user=actor_user,
        title="Master request status changed",
        body=(
            f"Master request '{updated.title}' moved to '{target_status.value}' "
            f"by {_full_name(actor_user)}."
        ),
        payload={
            "event": "master_request.status_change",
            "master_request_id": str(updated.id),
            "from": current_status.value,
            "to": target_status.value,
        },
        branch_id=updated.branch_id,
        request=request,
    )
    db.commit()
    return get_master_request_or_404(db, request_obj.id)


def add_master_request_comment(
    db: Session,
    actor_user: User,
    request_obj: MasterRequest,
    payload: MasterRequestCommentCreate,
    settings: Settings,
    *,
    request: Request | None = None,
) -> MasterRequestComment:
    _ensure_can_comment(actor_user, request_obj)

    comment = MasterRequestComment(
        master_request_id=request_obj.id,
        author_id=actor_user.id,
        body=payload.body.strip(),
    )
    db.add(comment)
    db.flush()

    write_audit_log(
        db,
        actor_user=actor_user,
        branch_id=request_obj.branch_id,
        entity_type="master_request",
        entity_id=str(request_obj.id),
        action="master_request.comment.create",
        payload={"comment_id": str(comment.id), "body": comment.body},
        request=request,
    )
    db.commit()
    db.refresh(comment)
    return comment


def report_master_geo_ping(
    db: Session,
    actor_user: User,
    request_obj: MasterRequest,
    payload: MasterGeoPingCreate,
    *,
    request: Request | None = None,
) -> MasterGeoPing:
    _ensure_can_change_status(actor_user, request_obj)

    if get_role_code(actor_user) == RoleCode.MASTER and request_obj.assignee_id != actor_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Master is not assigned")

    if request_obj.status not in GEO_TRACKED_MASTER_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Geo tracking is disabled for current status",
        )

    if not (-90 <= payload.latitude <= 90) or not (-180 <= payload.longitude <= 180):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Geo coordinates are out of range",
        )

    geo_ping = MasterGeoPing(
        master_request_id=request_obj.id,
        master_id=request_obj.assignee_id or actor_user.id,
        captured_at=payload.captured_at,
        latitude=payload.latitude,
        longitude=payload.longitude,
        accuracy_meters=payload.accuracy_meters,
        status_at_capture=request_obj.status,
    )
    db.add(geo_ping)

    request_obj.last_known_latitude = payload.latitude
    request_obj.last_known_longitude = payload.longitude
    request_obj.last_known_at = payload.captured_at
    db.add(request_obj)
    db.flush()

    write_audit_log(
        db,
        actor_user=actor_user,
        branch_id=request_obj.branch_id,
        entity_type="master_request",
        entity_id=str(request_obj.id),
        action="master_request.geo_ping",
        payload={
            "geo_ping_id": str(geo_ping.id),
            "latitude": payload.latitude,
            "longitude": payload.longitude,
        },
        request=request,
    )
    db.commit()
    db.refresh(geo_ping)
    return geo_ping


def upload_bso_attachment(
    db: Session,
    actor_user: User,
    request_obj: MasterRequest,
    *,
    file: UploadFile,
    attachment_type: AttachmentType,
    comment: str | None,
    settings: Settings,
    request: Request | None = None,
) -> BSOAttachment:
    _ensure_can_change_status(actor_user, request_obj)

    if request_obj.status not in {
        MasterRequestStatus.IN_PROGRESS,
        MasterRequestStatus.COMPLETED,
        MasterRequestStatus.HANDED_OVER,
    }:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="БСО можно прикрепить только к заявкам в работе или завершенным",
        )

    if not file.filename:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Filename is required")

    safe_name = Path(file.filename).name.replace(" ", "_")
    target_dir = Path(settings.media_root) / "master_requests" / str(request_obj.id)
    target_dir.mkdir(parents=True, exist_ok=True)
    relative_path = (
        Path("master_requests") / str(request_obj.id) / f"{uuid4().hex}_{safe_name}"
    )
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

    attachment = BSOAttachment(
        master_request_id=request_obj.id,
        uploaded_by_id=actor_user.id,
        attachment_type=attachment_type,
        file_path=relative_path.as_posix(),
        filename=safe_name,
        mime_type=file.content_type,
        size_bytes=total_written,
        comment=(comment.strip() if comment else None),
    )
    db.add(attachment)
    db.flush()

    write_audit_log(
        db,
        actor_user=actor_user,
        branch_id=request_obj.branch_id,
        entity_type="master_request",
        entity_id=str(request_obj.id),
        action="master_request.attachment.upload",
        payload={"attachment_id": str(attachment.id), "filename": attachment.filename},
        request=request,
    )
    db.commit()
    db.refresh(attachment)
    return attachment
