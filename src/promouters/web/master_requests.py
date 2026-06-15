"""Master requests admin (owner / branch_manager / dispatcher / director / master)."""
from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from promouters.core.config import Settings, get_settings
from promouters.db.session import get_db
from promouters.models.enums import AttachmentType, MasterRequestStatus
from promouters.models.operations import MasterRequest
from promouters.models.users import User
from promouters.schemas.master_requests import (
    MasterRequestCommentCreate,
    MasterRequestStatusChange,
)
from promouters.services import master_requests as svc
from promouters.web.deps import render, require_roles


logger = logging.getLogger(__name__)
router = APIRouter()

VIEW_ROLES = ("owner", "branch_manager", "master", "dispatcher", "director", "ad_director")


@router.get("/")
async def requests_list(
    request: Request,
    status_filter: str = "",
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(require_roles(*VIEW_ROLES)),
):
    role = user.role.code if user.role else None
    stmt = (
        select(MasterRequest)
        .options(
            joinedload(MasterRequest.branch),
            joinedload(MasterRequest.requester),
            joinedload(MasterRequest.assignee),
        )
        .order_by(MasterRequest.created_at.desc())
        .limit(500)
    )
    if role == "master":
        stmt = stmt.where(MasterRequest.assignee_id == user.id)
    elif role != "owner" and user.branch_id is not None:
        stmt = stmt.where(MasterRequest.branch_id == user.branch_id)
    if status_filter:
        try:
            stmt = stmt.where(MasterRequest.status == MasterRequestStatus(status_filter))
        except ValueError:
            pass
    requests = list(db.scalars(stmt))
    can_close = role in ("owner", "branch_manager", "dispatcher")
    return render(
        request,
        "master_requests_list.html",
        user=user,
        active_page="master_requests",
        requests=requests,
        status_filter=status_filter,
        statuses=list(MasterRequestStatus),
        can_close=can_close,
    )


@router.get("/{request_id}")
async def request_detail(
    request: Request,
    request_id: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(require_roles(*VIEW_ROLES)),
):
    try:
        target_id = UUID(request_id)
    except ValueError:
        return render(request, "404.html", user=user, status_code=404, what="Заявка")
    try:
        mr = svc.get_master_request_for_actor(db, user, target_id)
    except Exception:  # noqa: BLE001
        return render(request, "404.html", user=user, status_code=404, what="Заявка")
    return render(
        request,
        "master_request_detail.html",
        user=user,
        active_page="master_requests",
        request_obj=mr,
        statuses=list(MasterRequestStatus),
    )


@router.post("/{request_id}/status")
async def request_change_status(
    request: Request,
    request_id: str,
    new_status: str = Form(...),
    note: str = Form(default=""),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(require_roles(*VIEW_ROLES)),
):
    target_id = UUID(request_id)
    mr = svc.get_master_request_for_actor(db, user, target_id)
    try:
        status_change = MasterRequestStatusChange(
            status=MasterRequestStatus(new_status),
            note=note.strip() or None,
        )
        svc.change_master_request_status(
            db, user, mr, status_change, settings, request=request
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("master_request.change_status failed")
        return RedirectResponse(
            f"/admin/master-requests/{request_id}?error={getattr(exc, 'detail', 'status')}",
            status_code=302,
        )
    return RedirectResponse(f"/admin/master-requests/{request_id}", status_code=302)


@router.post("/{request_id}/comment")
async def request_add_comment(
    request: Request,
    request_id: str,
    body: str = Form(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(require_roles(*VIEW_ROLES)),
):
    target_id = UUID(request_id)
    mr = svc.get_master_request_for_actor(db, user, target_id)
    if body.strip():
        try:
            svc.add_master_request_comment(
                db, user, mr,
                MasterRequestCommentCreate(body=body.strip()),
                request=request,
            )
        except Exception:  # noqa: BLE001
            logger.exception("master_request.add_comment failed")
    return RedirectResponse(f"/admin/master-requests/{request_id}", status_code=302)


@router.post("/{request_id}/bso")
async def request_upload_bso(
    request: Request,
    request_id: str,
    file: UploadFile = File(...),
    comment: str = Form(default=""),
    attachment_type: str = Form(default="bso"),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(require_roles(*VIEW_ROLES)),
):
    target_id = UUID(request_id)
    mr = svc.get_master_request_for_actor(db, user, target_id)
    try:
        attach_enum = AttachmentType(attachment_type)
    except ValueError:
        attach_enum = AttachmentType.BSO
    try:
        svc.upload_bso_attachment(
            db, user, mr,
            file=file,
            attachment_type=attach_enum,
            comment=comment.strip() or None,
            settings=settings,
            request=request,
        )
    except Exception:  # noqa: BLE001
        logger.exception("master_request.upload_bso failed")
    return RedirectResponse(f"/admin/master-requests/{request_id}", status_code=302)


CLOSE_ROLES = ("owner", "branch_manager", "dispatcher")


@router.get("/{request_id}/close")
async def request_close_form(
    request: Request,
    request_id: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(require_roles(*CLOSE_ROLES)),
):
    try:
        target_id = UUID(request_id)
    except ValueError:
        return render(request, "404.html", user=user, status_code=404, what="Заявка")
    try:
        mr = svc.get_master_request_for_actor(db, user, target_id)
    except Exception:  # noqa: BLE001
        return render(request, "404.html", user=user, status_code=404, what="Заявка")
    return render(
        request,
        "master_request_close.html",
        user=user,
        active_page="master_requests",
        request_obj=mr,
    )


@router.post("/{request_id}/close")
async def request_close_submit(
    request: Request,
    request_id: str,
    sum_amount: str | None = Form(None),
    sd_price: str | None = Form(None),
    zpch_sum: str | None = Form(None),
    comment: str = Form(default=""),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(require_roles(*CLOSE_ROLES)),
):
    from decimal import Decimal

    target_id = UUID(request_id)
    mr = svc.get_master_request_for_actor(db, user, target_id)

    # Parse amounts
    def _parse_decimal(val: str | None) -> Decimal | None:
        if not val or not val.strip():
            return None
        try:
            return Decimal(val.strip())
        except Exception:
            return None

    final_amount = _parse_decimal(sum_amount)
    sd = _parse_decimal(sd_price)
    zpch = _parse_decimal(zpch_sum)

    # Update financial fields
    if final_amount is not None:
        mr.final_amount = final_amount
    if sd is not None or zpch is not None:
        note_parts = []
        if sd is not None:
            note_parts.append(f"СД: {sd}")
        if zpch is not None:
            note_parts.append(f"Запчасти: {zpch}")
        extra_note = "; ".join(note_parts)
    else:
        extra_note = ""

    # Change status to handed_over (closed)
    close_note = comment.strip() if comment.strip() else "Заявка закрыта"
    if extra_note:
        close_note = f"{close_note} ({extra_note})"

    try:
        status_change = MasterRequestStatusChange(
            status=MasterRequestStatus.HANDED_OVER,
            note=close_note,
        )
        svc.change_master_request_status(
            db, user, mr, status_change, settings, request=request
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("master_request.close failed")
        return RedirectResponse(
            f"/admin/master-requests/{request_id}?error={getattr(exc, 'detail', 'close_failed')}",
            status_code=302,
        )
    return RedirectResponse("/admin/cash", status_code=302)
