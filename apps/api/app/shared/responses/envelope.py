from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiEnvelope(BaseModel, Generic[T]):
    data: T


class HealthStatus(BaseModel):
    status: str


class HealthCheckResponse(BaseModel):
    status: str
    service: str
    environment: str
    version: str


class DatabaseHealthResponse(BaseModel):
    status: str
    database: str
