"""Align role keys and extend search criteria.

Revision ID: 0003_roles_and_search_filters
Revises: 0002_schema_extensions
Create Date: 2026-04-03
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op

revision = "0003_roles_and_search_filters"
down_revision = "0002_schema_extensions"
branch_labels = None
depends_on = None


def _has_column(table_name: str, column_name: str) -> bool:
    if context.is_offline_mode():
        return False
    inspector = sa.inspect(op.get_bind())
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def _drop_users_role_fk() -> None:
    if context.is_offline_mode():
        op.drop_constraint("fk_users_role_key", "users", type_="foreignkey")
        return

    inspector = sa.inspect(op.get_bind())
    for foreign_key in inspector.get_foreign_keys("users"):
        if foreign_key.get("referred_table") == "roles" and foreign_key.get(
            "constrained_columns"
        ) == ["role"]:
            op.drop_constraint(foreign_key["name"], "users", type_="foreignkey")
            break


def _create_users_role_fk() -> None:
    if not context.is_offline_mode():
        inspector = sa.inspect(op.get_bind())
        for foreign_key in inspector.get_foreign_keys("users"):
            if foreign_key.get("referred_table") == "roles" and foreign_key.get(
                "constrained_columns"
            ) == ["role"]:
                return
    op.create_foreign_key("fk_users_role_key", "users", "roles", ["role"], ["key"])


def _add_search_filter_columns(table_name: str) -> None:
    if not _has_column(table_name, "radius_km"):
        op.add_column(table_name, sa.Column("radius_km", sa.Integer(), nullable=True))
    if not _has_column(table_name, "max_rating"):
        op.add_column(table_name, sa.Column("max_rating", sa.Float(), nullable=True))
    if not _has_column(table_name, "max_reviews"):
        op.add_column(table_name, sa.Column("max_reviews", sa.Integer(), nullable=True))
    if not _has_column(table_name, "website_preference"):
        op.add_column(
            table_name,
            sa.Column(
                "website_preference",
                sa.String(length=32),
                nullable=False,
                server_default="any",
            ),
        )
    if not _has_column(table_name, "keyword_filter"):
        op.add_column(table_name, sa.Column("keyword_filter", sa.String(length=255), nullable=True))


def upgrade() -> None:
    _drop_users_role_fk()

    op.execute("UPDATE users SET role = 'agency_manager' WHERE role = 'manager'")
    op.execute("UPDATE users SET role = 'sales_user' WHERE role = 'sales'")
    op.execute(
        """
        UPDATE roles
        SET `key` = 'agency_manager',
            label = 'Agency Manager',
            description = 'Operational lead and scoring oversight.'
        WHERE `key` = 'manager'
        """
    )
    op.execute(
        """
        UPDATE roles
        SET `key` = 'sales_user',
            label = 'Sales User',
            description = 'Lead qualification and outreach execution.'
        WHERE `key` = 'sales'
        """
    )

    _create_users_role_fk()

    for table_name in ("search_requests", "search_jobs"):
        _add_search_filter_columns(table_name)

        op.execute(
            sa.text(
                f"""
                UPDATE {table_name}
                SET website_preference = CASE
                    WHEN require_website = true THEN 'must_have'
                    ELSE 'any'
                END
                """
            )
        )
        if context.is_offline_mode() or _has_column(table_name, "require_website"):
            op.drop_column(table_name, "require_website")
        op.alter_column(table_name, "website_preference", server_default=None)


def downgrade() -> None:
    for table_name in ("search_requests", "search_jobs"):
        op.add_column(
            table_name,
            sa.Column(
                "require_website",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )
        op.execute(
            sa.text(
                f"""
                UPDATE {table_name}
                SET require_website = CASE
                    WHEN website_preference = 'must_have' THEN true
                    ELSE false
                END
                """
            )
        )
        op.alter_column(table_name, "require_website", server_default=None)
        op.drop_column(table_name, "keyword_filter")
        op.drop_column(table_name, "website_preference")
        op.drop_column(table_name, "max_reviews")
        op.drop_column(table_name, "max_rating")
        op.drop_column(table_name, "radius_km")

    _drop_users_role_fk()

    op.execute("UPDATE users SET role = 'manager' WHERE role = 'agency_manager'")
    op.execute("UPDATE users SET role = 'sales' WHERE role = 'sales_user'")
    op.execute(
        """
        UPDATE roles
        SET `key` = 'manager',
            label = 'Manager',
            description = 'Operational lead and scoring oversight.'
        WHERE `key` = 'agency_manager'
        """
    )
    op.execute(
        """
        UPDATE roles
        SET `key` = 'sales',
            label = 'Sales',
            description = 'Lead qualification and outreach execution.'
        WHERE `key` = 'sales_user'
        """
    )

    _create_users_role_fk()
