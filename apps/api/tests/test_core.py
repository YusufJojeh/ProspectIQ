import logging

from sqlalchemy.orm import Session

from app.core.config import clear_settings_cache, get_settings
from app.core.database import get_db, get_session_factory, reset_database_state
from app.core.logging import SecretRedactionFilter


def test_settings_load_defaults() -> None:
    clear_settings_cache()
    settings = get_settings()

    assert settings.api_v1_prefix == "/api/v1"
    assert settings.database_url.startswith("mysql+pymysql://")


def test_settings_load_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("APP_NAME", "Core Test API")
    monkeypatch.setenv("WEB_ORIGIN", "http://localhost:3000/")
    clear_settings_cache()

    settings = get_settings()

    assert settings.app_name == "Core Test API"
    assert settings.web_origin == "http://localhost:3000"

    clear_settings_cache()


def test_db_dependency_yields_session() -> None:
    dependency = get_db()
    session = next(dependency)

    assert isinstance(session, Session)
    assert session.bind is not None

    dependency.close()


def test_session_factory_is_available() -> None:
    reset_database_state()

    factory = get_session_factory()

    assert factory is not None


def test_secret_redaction_filter_masks_query_api_keys() -> None:
    record = logging.LogRecord(
        name="httpx",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="HTTP Request: GET https://serpapi.com/search.json?api_key=super-secret&engine=google_maps",
        args=(),
        exc_info=None,
    )

    allowed = SecretRedactionFilter().filter(record)

    assert allowed is True
    assert "super-secret" not in record.getMessage()
    assert "api_key=[REDACTED]" in record.getMessage()
