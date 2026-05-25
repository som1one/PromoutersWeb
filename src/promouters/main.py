from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from promouters.api.router import api_router
from promouters.core.config import get_settings
from promouters.core.logging import configure_logging, get_logger
from promouters.services.reminders import lifespan as reminders_lifespan
from promouters.web.router import register_web_exception_handlers, web_router

settings = get_settings()
configure_logging(settings)
logger = get_logger(__name__)


@asynccontextmanager
async def app_lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
    async with reminders_lifespan(app, settings=settings):
        yield


app = FastAPI(
    title=settings.app_name,
    debug=settings.app_debug,
    version="0.1.0",
    lifespan=app_lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins if not settings.app_debug else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix=settings.api_v1_prefix)

media_path = urlparse(settings.media_url).path or "/media"
Path(settings.media_root).mkdir(parents=True, exist_ok=True)
app.mount(media_path, StaticFiles(directory=settings.media_root), name="media")

_admin_static_dir = Path(__file__).resolve().parent / "static"
_admin_static_dir.mkdir(parents=True, exist_ok=True)
app.mount(
    "/admin/static",
    StaticFiles(directory=str(_admin_static_dir)),
    name="admin_static",
)
app.include_router(web_router, prefix="/admin")
register_web_exception_handlers(app)


@app.get("/", tags=["system"])
def root() -> dict[str, str]:
    logger.debug("Root endpoint requested")
    return {"message": settings.app_name}
