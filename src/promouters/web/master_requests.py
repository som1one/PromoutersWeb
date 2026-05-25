"""Master requests admin (owner / branch_manager / master)."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from promouters.db.session import get_db
from promouters.models.operations import MasterRequest
from promouters.models.users import User
from promouters.web.deps import render, require_roles


router = APIRouter()


@router.get("/")
async def requests_list(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("owner", "branch_manager", "master")),
):
    stmt = (
        select(MasterRequest)
        .options(
            joinedload(MasterRequest.branch),
            joinedload(MasterRequest.requester),
            joinedload(MasterRequest.assignee),
        )
        .order_by(MasterRequest.created_at.desc())
        .limit(200)
    )
    role = user.role.code if user.role else None
    if role == "master":
        stmt = stmt.where(MasterRequest.assignee_id == user.id)
    requests = list(db.scalars(stmt))
    return render(
        request,
        "master_requests_list.html",
        user=user,
        active_page="master_requests",
        requests=requests,
    )


@router.get("/{request_id}")
async def request_detail(
    request: Request,
    request_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("owner", "branch_manager", "master")),
):
    try:
        target_id = UUID(request_id)
    except ValueError:
        return render(request, "404.html", user=user, status_code=404, what="Заявка")
    mr = db.scalar(
        select(MasterRequest)
        .options(
            joinedload(MasterRequest.branch),
            joinedload(MasterRequest.requester),
            joinedload(MasterRequest.assignee),
            joinedload(MasterRequest.comments),
            joinedload(MasterRequest.status_logs),
        )
        .where(MasterRequest.id == target_id)
    )
    if not mr:
        return render(request, "404.html", user=user, status_code=404, what="Заявка")
    return render(
        request,
        "master_request_detail.html",
        user=user,
        active_page="master_requests",
        request_obj=mr,
    )
