import logging
from typing import Any, cast

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response

from app.shared.responses import ErrorDetail, ErrorResponse

logger = logging.getLogger(__name__)


class ApiError(Exception):
    status_code = 400
    code = "api_error"

    def __init__(self, detail: str):
        self.detail = detail
        super().__init__(detail)


class NotFoundError(ApiError):
    status_code = 404
    code = "not_found"


class ConflictError(ApiError):
    status_code = 409
    code = "conflict"


class UnauthorizedError(ApiError):
    status_code = 401
    code = "unauthorized"


class ForbiddenError(ApiError):
    status_code = 403
    code = "forbidden"


class ServiceUnavailableError(ApiError):
    status_code = 503
    code = "service_unavailable"


class FeatureNotReadyError(ApiError):
    status_code = 501
    code = "feature_not_ready"


def build_error_response(
    *,
    status_code: int,
    code: str,
    detail: str,
    fields: list[dict[str, Any]] | None = None,
) -> JSONResponse:
    payload = ErrorResponse(error=ErrorDetail(code=code, detail=detail, fields=fields))
    return JSONResponse(status_code=status_code, content=payload.model_dump(exclude_none=True))


def _make_json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _make_json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_make_json_safe(item) for item in value]
    return str(value)


async def api_error_handler(_: Request, exc: Exception) -> Response:
    api_error = cast(ApiError, exc)
    return build_error_response(
        status_code=api_error.status_code,
        code=api_error.code,
        detail=api_error.detail,
    )


async def validation_error_handler(_: Request, exc: Exception) -> Response:
    validation_error = cast(RequestValidationError, exc)
    return build_error_response(
        status_code=422,
        code="validation_error",
        detail="The request payload is invalid.",
        fields=[_make_json_safe(dict(item)) for item in validation_error.errors()],
    )


async def http_error_handler(_: Request, exc: Exception) -> Response:
    http_error = cast(StarletteHTTPException, exc)
    return build_error_response(
        status_code=http_error.status_code,
        code="http_error",
        detail=str(http_error.detail),
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> Response:
    logger.exception(
        "request.unhandled_exception",
        extra={
            "method": request.method,
            "path": request.url.path,
        },
        exc_info=exc,
    )
    return build_error_response(
        status_code=500,
        code="internal_server_error",
        detail="An unexpected server error occurred.",
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, api_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)
