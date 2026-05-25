from sqlalchemy import text
from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends

from promouters.db.session import get_db
from promouters.schemas.health import HealthCheckResponse

router = APIRouter()


@router.get("/health", response_model=HealthCheckResponse)
def healthcheck() -> HealthCheckResponse:
    return HealthCheckResponse(status="ok")


@router.get("/ready", response_model=HealthCheckResponse)
def readiness_check(db: Session = Depends(get_db)) -> HealthCheckResponse:
    db.execute(text("SELECT 1"))
    return HealthCheckResponse(status="ok", database="up")

