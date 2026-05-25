"""Home page — role-aware landing under /admin/."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from promouters.db.session import get_db
from promouters.models.users import User
from promouters.services.orders import status_counts
from promouters.web.deps import get_web_user, render


router = APIRouter()


@router.get("/")
@router.get("/home")
async def home(
    request: Request,
    user: User = Depends(get_web_user),
    db: Session = Depends(get_db),
):
    role = user.role.code if user.role else None
    counts = status_counts(db) if role in {"owner", "director", "dispatcher", "branch_manager", "ad_director"} else {}
    return render(
        request,
        "home.html",
        user=user,
        active_page="home",
        status_counts=counts,
    )
