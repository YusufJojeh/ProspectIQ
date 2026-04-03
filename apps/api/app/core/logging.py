import json
import logging
import re
from contextvars import ContextVar, Token
from logging.config import dictConfig
from typing import Any

from app.core.config import Settings

correlation_id_context: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def bind_correlation_id(value: str | None) -> Token[str | None]:
    return correlation_id_context.set(value)


def clear_correlation_id(token: Token[str | None]) -> None:
    correlation_id_context.reset(token)


def get_correlation_id() -> str | None:
    return correlation_id_context.get()


class CorrelationIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "correlation_id"):
            record.correlation_id = get_correlation_id()
        return True


class SecretRedactionFilter(logging.Filter):
    _PATTERNS = (
        (
            re.compile(r"([?&](?:api_key|token|access_token|client_secret|password)=)[^&\s]+"),
            r"\1[REDACTED]",
        ),
        (
            re.compile(
                r'("?(?:api_key|token|access_token|client_secret|password)"?\s*[:=]\s*")([^"]+)(")',
                re.IGNORECASE,
            ),
            r"\1[REDACTED]\3",
        ),
        (
            re.compile(r"(Bearer\s+)[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE),
            r"\1[REDACTED]",
        ),
    )

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        redacted = message
        for pattern, replacement in self._PATTERNS:
            redacted = pattern.sub(replacement, redacted)
        if redacted != message:
            record.msg = redacted
            record.args = ()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "correlation_id") and record.correlation_id:
            payload["correlation_id"] = record.correlation_id
        if hasattr(record, "method"):
            payload["method"] = record.method
        if hasattr(record, "path"):
            payload["path"] = record.path
        if hasattr(record, "status_code"):
            payload["status_code"] = record.status_code
        if hasattr(record, "duration_ms"):
            payload["duration_ms"] = record.duration_ms
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=True)


def setup_logging(settings: Settings) -> None:
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "json": {
                    "()": JsonFormatter,
                }
            },
            "filters": {
                "correlation_id": {
                    "()": CorrelationIdFilter,
                },
                "redact_secrets": {
                    "()": SecretRedactionFilter,
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "json",
                    "filters": ["correlation_id", "redact_secrets"],
                }
            },
            "root": {"handlers": ["console"], "level": settings.log_level.upper()},
            "loggers": {
                "uvicorn": {
                    "handlers": ["console"],
                    "level": settings.log_level.upper(),
                    "propagate": False,
                },
                "uvicorn.error": {
                    "handlers": ["console"],
                    "level": settings.log_level.upper(),
                    "propagate": False,
                },
                "uvicorn.access": {
                    "handlers": ["console"],
                    "level": settings.log_level.upper(),
                    "propagate": False,
                },
            },
        }
    )
