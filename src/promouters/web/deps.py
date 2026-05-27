"""Cookie-based auth dependencies for the Jinja2 admin under /admin.

The web layer never imports from ``api/deps.py``: API uses bearer tokens, the
web layer uses ``access_token``/``refresh_token`` cookies (httpOnly, SameSite=Lax,
Secure in prod). ``WebAuthException`` is converted to a redirect by the
exception handler registered in ``web.router``.
"""
from __future__ import annotations

from pathlib import Path
from uuid import UUID

from fastapi import Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from promouters.core.config import Settings, get_settings
from promouters.db.session import get_db
from promouters.models.enums import UserStatus
from promouters.models.users import User
from promouters.utils.jwt import decode_jwt_token


TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"
CHALLENGE_COOKIE = "login_challenge_id"


class WebAuthException(Exception):
    """Raised when web cookie auth fails; converted to a 302 by the handler."""

    def __init__(self, *, next_url: str | None = None) -> None:
        self.next_url = next_url
        super().__init__("Web auth required")


class WebForbiddenException(Exception):
    """Raised when a logged-in user lacks the required role for a view."""


def _decode_access_token(token: str, settings: Settings) -> dict:
    return decode_jwt_token(
        token=token,
        secret=settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def get_web_user(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    token = request.cookies.get(ACCESS_COOKIE)
    if not token:
        raise WebAuthException(next_url=str(request.url.path))

    try:
        payload = _decode_access_token(token, settings)
    except Exception as exc:  # noqa: BLE001 — decode_jwt_token raises bare Exception
        raise WebAuthException(next_url=str(request.url.path)) from exc

    try:
        user_id = UUID(str(payload["user_id"]))
    except (KeyError, ValueError) as exc:
        raise WebAuthException(next_url=str(request.url.path)) from exc

    user = db.scalar(
        select(User)
        .options(joinedload(User.role), joinedload(User.branch))
        .where(User.id == user_id)
    )
    if user is None or user.status != UserStatus.ACTIVE:
        raise WebAuthException(next_url=str(request.url.path))
    return user


def get_optional_web_user(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User | None:
    token = request.cookies.get(ACCESS_COOKIE)
    if not token:
        return None
    try:
        payload = _decode_access_token(token, settings)
        user_id = UUID(str(payload["user_id"]))
    except Exception:  # noqa: BLE001
        return None
    user = db.scalar(
        select(User)
        .options(joinedload(User.role), joinedload(User.branch))
        .where(User.id == user_id)
    )
    if user is None or user.status != UserStatus.ACTIVE:
        return None
    return user


def require_roles(*codes: str):
    """Dependency factory: 403→redirect/Forbidden unless user's role.code is allowed."""

    allowed = set(codes)

    def _dep(user: User = Depends(get_web_user)) -> User:
        role_code = user.role.code if user.role else None
        if role_code not in allowed and not user.is_superuser:
            raise WebForbiddenException()
        return user

    return _dep


def render(
    request: Request,
    template_name: str,
    *,
    user: User | None = None,
    **context,
) -> object:
    """Wrapper around ``templates.TemplateResponse`` that always injects ``user`` and ``request``.

    Templates expect ``user`` (current logged-in User or None) and ``request`` to
    be available in the rendering context.

    Также вычисляет ``unread_count`` для бейджа уведомлений, если есть user и не
    задан явно в контексте.
    """
    payload: dict = {"request": request, "user": user, "unread_count": 0}
    if user is not None and "unread_count" not in context:
        try:
            from sqlalchemy import func, select  # local import to avoid cycle
            from promouters.db.session import SessionLocal
            from promouters.models.enums import NotificationStatus
            from promouters.models.operations import Notification

            with SessionLocal() as session:
                count = session.scalar(
                    select(func.count(Notification.id)).where(
                        Notification.user_id == user.id,
                        Notification.status != NotificationStatus.READ,
                    )
                )
                payload["unread_count"] = int(count or 0)
        except Exception:  # noqa: BLE001
            payload["unread_count"] = 0
    payload.update(context)
    return templates.TemplateResponse(template_name, payload)


def set_auth_cookies(
    response,
    *,
    access_token: str,
    refresh_token: str,
    settings: Settings,
) -> None:
    secure = bool(getattr(settings, "web_cookie_secure", False))
    response.set_cookie(
        key=ACCESS_COOKIE,
        value=access_token,
        max_age=settings.jwt_expiration_time,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=refresh_token,
        max_age=settings.jwt_refresh_expiration_time,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )


def clear_auth_cookies(response) -> None:
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path="/")
    response.delete_cookie(CHALLENGE_COOKIE, path="/")
