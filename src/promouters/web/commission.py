"""Commission tier admin (owner only) — read/write system_settings.commission_config."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from promouters.db.session import get_db
from promouters.models.users import User
from promouters.services import commission as commission_svc
from promouters.web.deps import render, require_roles


router = APIRouter()


@router.get("/")
async def commission_view(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("owner")),
):
    settings = commission_svc.load_settings(db)
    return render(
        request,
        "commission.html",
        user=user,
        active_page="commission",
        settings=settings,
        settings_json=json.dumps(settings, ensure_ascii=False, indent=2),
    )


@router.post("/")
async def commission_save(
    raw_json: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("owner")),  # noqa: ARG001
):
    try:
        parsed = json.loads(raw_json)
    except json.JSONDecodeError:
        return RedirectResponse("/admin/commission?error=invalid_json", status_code=302)
    commission_svc.save_settings(db, parsed)
    return RedirectResponse("/admin/commission?saved=1", status_code=302)
