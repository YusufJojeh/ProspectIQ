from fastapi import APIRouter, FastAPI

from app.core.config import get_settings
from app.core.database import check_database_connection
from app.core.errors import register_exception_handlers
from app.core.logging import setup_logging
from app.core.middleware import add_cors_middleware, add_http_middleware
from app.modules.admin.api import router as admin_router
from app.modules.auth.api import router as auth_router
from app.modules.leads.api import router as leads_router
from app.modules.search_jobs.api import router as search_jobs_router
from app.modules.users.api import router as users_router
from app.shared.responses import DatabaseHealthResponse, HealthCheckResponse


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings)
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        summary="Backend foundation for the ProspectIQ lead intelligence platform.",
    )
    add_cors_middleware(app)
    add_http_middleware(app)
    register_exception_handlers(app)

    api_v1 = APIRouter(prefix=settings.api_v1_prefix)

    @api_v1.get("/health", response_model=HealthCheckResponse, tags=["health"])
    def healthcheck() -> HealthCheckResponse:
        return HealthCheckResponse(
            status="ok",
            service=settings.app_name,
            environment=settings.app_env,
            version=app.version,
        )

    @api_v1.get("/health/db", response_model=DatabaseHealthResponse, tags=["health"])
    def database_healthcheck() -> DatabaseHealthResponse:
        if settings.enable_db_healthcheck:
            check_database_connection()
        return DatabaseHealthResponse(status="ok", database="connected")

    app.include_router(api_v1)
    app.include_router(auth_router)
    app.include_router(users_router)
    app.include_router(search_jobs_router)
    app.include_router(leads_router)
    app.include_router(admin_router)
    return app


app = create_app()
