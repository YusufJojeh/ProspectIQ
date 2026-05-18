from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from alembic.ddl.impl import DefaultImpl
from sqlalchemy import Column, MetaData, PrimaryKeyConstraint, String, Table, engine_from_config, inspect, pool, text

from app.core.config import get_settings
from app.core.database import Base
from app.modules.admin import models as admin_models  # noqa: F401

# Import models so Base.metadata is populated for autogenerate.
from app.modules.ai_analysis import models as ai_models  # noqa: F401
from app.modules.assistant import models as assistant_models  # noqa: F401
from app.modules.audit_logs import models as audit_models  # noqa: F401
from app.modules.billing import models as billing_models  # noqa: F401
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
ALEMBIC_VERSION_NUM_LENGTH = 128


def _extended_version_table_impl(
    self: DefaultImpl,
    *,
    version_table: str,
    version_table_schema: str | None,
    version_table_pk: bool,
    **_: object,
) -> Table:
    table = Table(
        version_table,
        MetaData(),
        Column("version_num", String(ALEMBIC_VERSION_NUM_LENGTH), nullable=False),
        schema=version_table_schema,
    )
    if version_table_pk:
        table.append_constraint(
            PrimaryKeyConstraint("version_num", name=f"{version_table}_pkc")
        )
    return table


DefaultImpl.version_table_impl = _extended_version_table_impl


def get_url() -> str:
    return get_settings().database_url


def run_migrations_offline() -> None:
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        transaction_per_migration=True,
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
        is_mysql_family = connection.dialect.name in {"mysql", "mariadb"}
        inspector = inspect(connection)
        if is_mysql_family and inspector.has_table("alembic_version"):
            version_column = next(
                (
                    column
                    for column in inspector.get_columns("alembic_version")
                    if column.get("name") == "version_num"
                ),
                None,
            )
            current_length = getattr(version_column.get("type"), "length", None) if version_column else None
            if current_length is not None and current_length < ALEMBIC_VERSION_NUM_LENGTH:
                connection.execute(
                    text(
                        "ALTER TABLE alembic_version "
                        f"MODIFY version_num VARCHAR({ALEMBIC_VERSION_NUM_LENGTH}) NOT NULL"
                    )
                )
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            transaction_per_migration=True,
        )
        with context.begin_transaction():
            context.run_migrations()
        if is_mysql_family and connection.in_transaction():
            connection.commit()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
