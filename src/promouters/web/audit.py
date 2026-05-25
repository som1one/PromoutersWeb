"""Audit log viewer (owner only)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from promouters.db.session import get_db
from promouters.models.operations import AuditLog
from promouters.models.users import User
from promouters.web.deps import render, require_roles


router = APIRouter()


@router.get("/")
async def audit_list(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("owner")),
):
    logs = list(
        db.scalars(
            select(AuditLog)
            .options(joinedload(AuditLog.actor), joinedload(AuditLog.branch))
            .order_by(AuditLog.created_at.desc())
            .limit(300)
        )
    )
    return render(
        request,
        "audit_log.html",
        user=user,
        active_page="audit",
        logs=logs,
    )
