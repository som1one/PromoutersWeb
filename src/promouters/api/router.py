from fastapi import APIRouter

from promouters.api.v1.audit_logs import router as audit_logs_router
from promouters.api.v1.auth import router as auth_router
from promouters.api.v1.branches import router as branches_router
from promouters.api.v1.expense_plans import router as expense_plans_router
from promouters.api.v1.finance import router as finance_router
from promouters.api.v1.health import router as health_router
from promouters.api.v1.master_requests import router as master_requests_router
from promouters.api.v1.notifications import router as notifications_router
from promouters.api.v1.roles import router as roles_router
from promouters.api.v1.routes import router as routes_router
from promouters.api.v1.users import router as users_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(audit_logs_router)
api_router.include_router(branches_router)
api_router.include_router(expense_plans_router)
api_router.include_router(finance_router)
api_router.include_router(health_router, tags=["health"])
api_router.include_router(master_requests_router)
api_router.include_router(notifications_router)
api_router.include_router(roles_router)
api_router.include_router(routes_router)
api_router.include_router(users_router)
