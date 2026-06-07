"""Company profile form ported from PythonProject2/company_form."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from promouters.core.config import Settings, get_settings
from promouters.db.session import get_db
from promouters.models.users import User
from promouters.schemas.company_profile import CompanyProfileData
from promouters.services import company_profile as company_svc
from promouters.web.deps import render, require_roles


router = APIRouter()


ALLOWED_ROLES = (
    "owner",
    "director",
    "dispatcher",
    "branch_manager",
    "ad_director",
    "master",
)

ALL_CATEGORIES = [
    "Автоуслуги",
    "Услуги строителя",
    "Красота",
    "Бытовые услуги",
    "Финансовые услуги",
    "Парфюм",
    "Автотовары",
]


@router.get("/form")
async def company_form_page(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*ALLOWED_ROLES)),
):
    return render(
        request,
        "company_form.html",
        user=user,
        active_page="company",
        form_data=company_svc.load_profile(db),
        categories=ALL_CATEGORIES,
        flash_success="Данные компании сохранены." if request.query_params.get("saved") else None,
    )


@router.post("/form")
async def company_form_submit(
    request: Request,
    website: str | None = Form(None),
    social_networks: str | None = Form(None),
    categories: list[str] = Form(default=[]),
    description: str | None = Form(None),
    prepayment_available: bool = Form(False),
    phone_number: str | None = Form(None),
    photos: list[UploadFile] = File(default=[]),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(require_roles(*ALLOWED_ROLES)),
):
    saved_photo_paths: list[str] = []
    if len([item for item in photos if item.filename]) > 6:
        return render(
            request,
            "company_form.html",
            user=user,
            active_page="company",
            categories=ALL_CATEGORIES,
            form_data=SimpleNamespace(
                website=website or None,
                social_networks=[s.strip() for s in (social_networks or "").split(",") if s.strip()],
                categories=categories,
                photos=[],
                description=description or None,
                prepayment_available=prepayment_available,
                phone_number=phone_number or None,
            ),
            flash_error="Максимум 6 фотографий.",
        )

    target_dir = Path(settings.media_root) / "company_profile"
    target_dir.mkdir(parents=True, exist_ok=True)
    for item in photos:
        if not item.filename:
            continue
        safe_name = Path(item.filename).name.replace(" ", "_")
        suffix = Path(safe_name).suffix or ".jpg"
        target_name = f"{uuid4().hex}{suffix}"
        target_path = target_dir / target_name
        target_path.write_bytes(await item.read())
        saved_photo_paths.append(str(Path("company_profile") / target_name).replace("\\", "/"))

    try:
        profile = CompanyProfileData(
            website=(website or "").strip() or None,
            social_networks=[s.strip() for s in (social_networks or "").split(",") if s.strip()],
            categories=categories,
            photos=saved_photo_paths or company_svc.load_profile(db).photos,
            description=(description or "").strip() or None,
            prepayment_available=prepayment_available,
            phone_number=(phone_number or "").strip() or None,
        )
    except ValidationError as exc:
        messages = []
        for error in exc.errors():
            field = error.get("loc", ["поле"])[-1]
            messages.append(f"{field}: {error.get('msg', 'ошибка')}")
        return render(
            request,
            "company_form.html",
            user=user,
            active_page="company",
            categories=ALL_CATEGORIES,
            form_data=SimpleNamespace(
                website=(website or "").strip() or None,
                social_networks=[s.strip() for s in (social_networks or "").split(",") if s.strip()],
                categories=categories,
                photos=saved_photo_paths,
                description=(description or "").strip() or None,
                prepayment_available=prepayment_available,
                phone_number=(phone_number or "").strip() or None,
            ),
            flash_error="; ".join(messages),
        )

    company_svc.save_profile(db, profile)
    return RedirectResponse("/admin/company/form?saved=1", status_code=302)
