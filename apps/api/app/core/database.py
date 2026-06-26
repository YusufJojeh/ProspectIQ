from collections.abc import Generator, Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


def create_db_engine(
    database_url: str | None = None,
    *,
    echo: bool | None = None,
) -> Engine:
    settings = get_settings()
    url = database_url or settings.database_url
    engine_kwargs: dict[str, object] = {
        "echo": settings.sql_echo if echo is None else echo,
        "future": True,
        "pool_pre_ping": True,
        "pool_recycle": 1800,
    }

    if make_url(url).get_backend_name() == "sqlite":
        engine_kwargs["connect_args"] = {"check_same_thread": False}
        engine_kwargs.pop("pool_recycle")

    return create_engine(
        url,
        **engine_kwargs,
    )


@lru_cache
def get_engine() -> Engine:
    return create_db_engine()


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(
        bind=get_engine(),
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        class_=Session,
    )


SessionLocal = get_session_factory()


def get_session() -> Session:
    return get_session_factory()()


@contextmanager
def session_scope() -> Iterator[Session]:
    session = get_session()
    try:
        yield session
    finally:
        session.close()


def get_db() -> Generator[Session, None, None]:
    with session_scope() as session:
        yield session


def check_database_connection() -> bool:
    with get_engine().connect() as connection:
        connection.execute(text("SELECT 1"))
    return True


def dispose_engine() -> None:
    if get_engine.cache_info().currsize:
        get_engine().dispose()


def reset_database_state() -> None:
    dispose_engine()
    get_session_factory.cache_clear()
    get_engine.cache_clear()


__all__ = [
    "Base",
    "SessionLocal",
    "check_database_connection",
    "create_db_engine",
    "dispose_engine",
    "get_db",
    "get_engine",
    "get_session",
    "get_session_factory",
    "reset_database_state",
    "session_scope",
]
