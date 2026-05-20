from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.config import get_settings
from app.core.errors import register_exception_handlers


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version=settings.app_version)
    register_exception_handlers(app)
    app.include_router(api_router, prefix="/api")
    app.mount("/storage", StaticFiles(directory=settings.storage_root, check_dir=False), name="storage")
    return app


app = create_app()
