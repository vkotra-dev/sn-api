from fastapi import APIRouter
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.auth.router import router as auth_router
from app.core.errors import APIError
from app.common.responses import success_response
from app.database.session import get_engine
from app.layouts.router import public_router as public_layouts_router
from app.layouts.router import router as layouts_router
from app.plots.router import router as plots_router

api_router = APIRouter()


@api_router.get("/health", tags=["health"])
async def health() -> dict[str, object]:
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise APIError("SERVICE_UNAVAILABLE", "Database unavailable", status_code=503) from exc

    return success_response({"status": "ok", "database": "ok"})

api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(layouts_router, tags=["layouts"])
api_router.include_router(public_layouts_router, tags=["layouts"])
api_router.include_router(plots_router, tags=["plots"])
