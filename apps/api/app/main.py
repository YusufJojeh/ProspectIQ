import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI

from app.core.config import get_settings
from app.core.database import check_database_connection, dispose_engine
from app.core.errors import ServiceUnavailableError, register_exception_handlers
from app.core.logging import setup_logging
from app.core.middleware import add_cors_middleware, add_http_middleware
from app.modules.admin.api import router as admin_router
from app.modules.ai_analysis.api import router as ai_analysis_router
from app.modules.audit_logs.api import router as audit_logs_router
from app.modules.auth.api import router as auth_router
from app.modules.exports.api import router as exports_router
from app.modules.leads.api import router as leads_router
from app.modules.outreach.api import router as outreach_router
from app.modules.search_jobs.api import router as search_jobs_router
from app.modules.users.api import router as users_router
from app.shared.responses import DatabaseHealthResponse, HealthCheckResponse

logger = logging.getLogger(__name__)


@asynccontextmanager
async def app_lifespan(_: FastAPI) -> AsyncIterator[None]:
    logger.info("app.startup")
    try:
        yield
    finally:
        dispose_engine()
        logger.info("app.shutdown")


def build_core_router() -> APIRouter:
    settings = get_settings()
    router = APIRouter(prefix=settings.api_v1_prefix)

    @router.get("/health", response_model=HealthCheckResponse, tags=["health"])
    def healthcheck() -> HealthCheckResponse:
        return HealthCheckResponse(
            status="ok",
            service=settings.app_name,
            environment=settings.app_env,
            version="0.1.0",
        )

    @router.get("/health/db", response_model=DatabaseHealthResponse, tags=["health"])
    def database_healthcheck() -> DatabaseHealthResponse:
        if not settings.enable_db_healthcheck:
            return DatabaseHealthResponse(status="ok", database="disabled")
        try:
            check_database_connection()
        except Exception as exc:
            raise ServiceUnavailableError("Database connectivity check failed.") from exc
        return DatabaseHealthResponse(status="ok", database="connected")

    return router


def register_application_routers(app: FastAPI) -> None:
    app.include_router(build_core_router())
    app.include_router(auth_router)
    app.include_router(users_router)
    app.include_router(search_jobs_router)
    app.include_router(leads_router)
    app.include_router(ai_analysis_router)
    app.include_router(outreach_router)
    app.include_router(admin_router)
    app.include_router(audit_logs_router)
    app.include_router(exports_router)


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings)
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        summary="Backend foundation for the LeadScope AI lead intelligence platform.",
        lifespan=app_lifespan,
    )
    app.state.settings = settings
    add_cors_middleware(app)
    add_http_middleware(app)
    register_exception_handlers(app)
    register_application_routers(app)
    return app


app = create_app()
