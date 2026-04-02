from collections.abc import Callable

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


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


class FeatureNotReadyError(ApiError):
    status_code = 501
    code = "feature_not_ready"


def _build_handler() -> Callable[[Request, ApiError], JSONResponse]:
    def handler(_: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "detail": exc.detail}},
        )

    return handler


def _build_validation_handler() -> Callable[[Request, RequestValidationError], JSONResponse]:
    def handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "detail": "The request payload is invalid.",
                    "fields": exc.errors(),
                }
            },
        )

    return handler


def _build_http_handler() -> Callable[[Request, StarletteHTTPException], JSONResponse]:
    def handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": "http_error",
                    "detail": str(exc.detail),
                }
            },
        )

    return handler


def _build_unhandled_handler() -> Callable[[Request, Exception], JSONResponse]:
    def handler(_: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_server_error",
                    "detail": "An unexpected server error occurred.",
                }
            },
        )

    return handler


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, _build_handler())
    app.add_exception_handler(RequestValidationError, _build_validation_handler())
    app.add_exception_handler(StarletteHTTPException, _build_http_handler())
    app.add_exception_handler(Exception, _build_unhandled_handler())
