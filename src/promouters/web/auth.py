"""Web auth flow under /admin: login, SMS verification, logout.

Reuses the existing JWT + SMS service functions from ``promouters.services.auth``.
Sets/clears httpOnly cookies; doesn't touch the bearer-token API flow.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from promouters.core.config import Settings, get_settings
from promouters.db.session import get_db
from promouters.services.auth import create_login_flow, verify_login_code
from promouters.web.deps import (
    ACCESS_COOKIE,
    CHALLENGE_COOKIE,
    clear_auth_cookies,
    render,
    set_auth_cookies,
)


router = APIRouter()


def _safe_next(next_url: str | None) -> str:
    if next_url and next_url.startswith("/admin"):
        return next_url
    return "/admin/"


@router.get("/login")
async def login_form(request: Request, next: str | None = None):
    if request.cookies.get(ACCESS_COOKIE):
        return RedirectResponse(_safe_next(next), status_code=302)
    return render(request, "admin_login.html", flash_error=None, phone=None, next=next or "")


@router.post("/login")
async def login_submit(
    request: Request,
    phone: str = Form(...),
    password: str = Form(...),
    next: str = Form(default=""),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    try:
        result = create_login_flow(db, settings, phone=phone, password=password)
    except Exception as exc:  # noqa: BLE001 — display friendly error
        message = getattr(exc, "detail", None) or "Не удалось войти. Проверьте телефон и пароль."
        return render(
            request,
            "admin_login.html",
            flash_error=str(message),
            phone=phone,
            next=next,
        )

    if result.requires_sms_verification:
        response = RedirectResponse("/admin/verify-sms", status_code=302)
        # Short-lived cookie to carry the challenge id between the two steps.
        secure = not getattr(settings, "debug", True)
        response.set_cookie(
            CHALLENGE_COOKIE,
            value=str(result.challenge_id),
            max_age=settings.auth_sms_code_ttl_seconds,
            httponly=True,
            secure=secure,
            samesite="lax",
            path="/",
        )
        if next:
            response.set_cookie("login_next", value=next, max_age=600, httponly=True, samesite="lax", path="/")
        return response

    response = RedirectResponse(_safe_next(next), status_code=302)
    set_auth_cookies(
        response,
        access_token=result.access_token,
        refresh_token=result.refresh_token,
        settings=settings,
    )
    return response


@router.get("/verify-sms")
async def verify_sms_form(request: Request):
    if not request.cookies.get(CHALLENGE_COOKIE):
        return RedirectResponse("/admin/login", status_code=302)
    return render(request, "sms_verify.html", flash_error=None)


@router.post("/verify-sms")
async def verify_sms_submit(
    request: Request,
    code: str = Form(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    challenge_id_str = request.cookies.get(CHALLENGE_COOKIE)
    if not challenge_id_str:
        return RedirectResponse("/admin/login", status_code=302)
    try:
        challenge_id = UUID(challenge_id_str)
    except ValueError:
        return RedirectResponse("/admin/login", status_code=302)

    try:
        tokens = verify_login_code(db, settings, challenge_id, code)
    except Exception as exc:  # noqa: BLE001
        message = getattr(exc, "detail", None) or "Неверный или просроченный код."
        return render(request, "sms_verify.html", flash_error=str(message))

    next_url = request.cookies.get("login_next") or "/admin/"
    response = RedirectResponse(_safe_next(next_url), status_code=302)
    set_auth_cookies(
        response,
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        settings=settings,
    )
    response.delete_cookie(CHALLENGE_COOKIE, path="/")
    response.delete_cookie("login_next", path="/")
    return response


@router.post("/logout")
async def logout(request: Request):  # noqa: ARG001
    response = RedirectResponse("/admin/login", status_code=302)
    clear_auth_cookies(response)
    return response
