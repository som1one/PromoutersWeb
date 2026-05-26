"""Home page — role-aware landing under /admin/."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from promouters.db.session import get_db
from promouters.models.users import User
from promouters.services.orders import status_counts
from promouters.web.deps import get_web_user, render


logger = logging.getLogger(__name__)
router = APIRouter()


SERVICE_ROLES = {"owner", "director", "dispatcher", "branch_manager", "ad_director"}


@router.get("/")
@router.get("/home")
async def home(
    request: Request,
    user: User = Depends(get_web_user),
    db: Session = Depends(get_db),
):
    role = user.role.code if user.role else None
    counts: dict[str, int] = {}
    if role in SERVICE_ROLES:
        try:
            counts = status_counts(db)
        except Exception:  # noqa: BLE001
            logger.exception("status_counts failed on dashboard")
            counts = {}
    return render(
        request,
        "home.html",
        user=user,
        active_page="home",
        status_counts=counts,
    )
