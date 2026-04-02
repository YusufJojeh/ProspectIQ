from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db


def test_settings_load_defaults() -> None:
    settings = get_settings()

    assert settings.api_v1_prefix == "/api/v1"
    assert settings.database_url.startswith("mysql+pymysql://")


def test_db_dependency_yields_session() -> None:
    dependency = get_db()
    session = next(dependency)

    assert isinstance(session, Session)

    dependency.close()
