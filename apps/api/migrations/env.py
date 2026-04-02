from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import get_settings
from app.core.database import Base

# Import models so Base.metadata is populated for autogenerate.
from app.modules.ai_analysis import models as ai_models  # noqa: F401
from app.modules.audit_logs import models as audit_models  # noqa: F401
from app.modules.leads import models as lead_models  # noqa: F401
from app.modules.outreach import models as outreach_models  # noqa: F401
from app.modules.provider_serpapi import models as provider_models  # noqa: F401
from app.modules.scoring import models as scoring_models  # noqa: F401
from app.modules.search_jobs import models as search_job_models  # noqa: F401
from app.modules.users import models as user_models  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url() -> str:
    return get_settings().database_url


def run_migrations_offline() -> None:
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = get_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
