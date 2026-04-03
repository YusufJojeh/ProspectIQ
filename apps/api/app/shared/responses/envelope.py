from typing import Any

from pydantic import BaseModel


class ApiEnvelope[T](BaseModel):
    data: T


class ErrorDetail(BaseModel):
    code: str
    detail: str
    fields: list[dict[str, Any]] | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


class HealthCheckResponse(BaseModel):
    status: str
    service: str
    environment: str
    version: str


class DatabaseHealthResponse(BaseModel):
    status: str
    database: str
