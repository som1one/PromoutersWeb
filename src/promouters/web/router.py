"""Aggregator for all /admin Jinja2 routers.

``main.py`` mounts this with ``app.include_router(web_router, prefix="/admin")``.
Also registers the WebAuthException / WebForbiddenException handlers via
``register_web_exception_handlers(app)``.
"""
from __future__ import annotations

from fastapi import APIRouter, FastAPI, Request, status
from fastapi.responses import RedirectResponse

from promouters.web.deps import WebAuthException, WebForbiddenException, render
from promouters.web import (
    audit as audit_router,
    auth as auth_router,
    branches as branches_router,
    cash as cash_router,
    cities as cities_router,
    company as company_router,
    dashboard as dashboard_router,
    expense_plans as expense_plans_router,
    legacy as legacy_router,
    master_requests as master_requests_router,
    masters as masters_router,
    notifications as notifications_router,
    orders as orders_router,
    payouts as payouts_router,
    promoters as promoters_router,
    routes_promoter as routes_promoter_router,
    sd as sd_router,
    stats as stats_router,
    users as users_router,
)


web_router = APIRouter()

# Order matters only for path-overlap visibility — FastAPI matches exact paths.
web_router.include_router(auth_router.router)
web_router.include_router(legacy_router.router)
web_router.include_router(dashboard_router.router)
web_router.include_router(orders_router.router, prefix="/orders")
web_router.include_router(masters_router.router, prefix="/masters")
web_router.include_router(promoters_router.router, prefix="/promoters")
web_router.include_router(cities_router.router, prefix="/cities")
web_router.include_router(company_router.router, prefix="/company")
web_router.include_router(branches_router.router, prefix="/branches")
web_router.include_router(cash_router.router, prefix="/cash")
web_router.include_router(sd_router.router, prefix="/sd")
web_router.include_router(stats_router.router, prefix="/stats")
web_router.include_router(users_router.router, prefix="/users")
web_router.include_router(routes_promoter_router.router, prefix="/routes")
web_router.include_router(payouts_router.router, prefix="/payouts")
web_router.include_router(expense_plans_router.router, prefix="/expense-plans")
web_router.include_router(master_requests_router.router, prefix="/master-requests")
web_router.include_router(audit_router.router, prefix="/audit")
web_router.include_router(notifications_router.router, prefix="/notifications")


def register_web_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(WebAuthException)
    async def _web_auth_handler(request: Request, exc: WebAuthException):  # noqa: ARG001
        next_url = exc.next_url or "/admin/"
        if not next_url.startswith("/admin"):
            next_url = "/admin/"
        target = "/admin/login"
        if next_url and next_url != "/admin/":
            target = f"/admin/login?next={next_url}"
        return RedirectResponse(target, status_code=status.HTTP_302_FOUND)

    @app.exception_handler(WebForbiddenException)
    async def _web_forbidden_handler(request: Request, exc: WebForbiddenException):  # noqa: ARG001
        return render(request, "forbidden.html", user=None, status_code=403)
