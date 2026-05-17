"""Harden usage counters and lead source integrity.

Revision ID: 0008_db_hardening_integrity
Revises: 0007_service_catalog
Create Date: 2026-05-18
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op

revision = "0008_db_hardening_integrity"
down_revision = "0007_service_catalog"
branch_labels = None
depends_on = None


def _duplicate_usage_counter_rows(bind: sa.engine.Connection) -> list[sa.Row[tuple[object, ...]]]:
    return list(
        bind.execute(
            sa.text(
                """
                SELECT
                    workspace_id,
                    metric_key,
                    period_start,
                    period_end,
                    COUNT(*) AS row_count
                FROM usage_counters
                GROUP BY workspace_id, metric_key, period_start, period_end
                HAVING COUNT(*) > 1
                ORDER BY workspace_id, metric_key, period_start, period_end
                LIMIT 20
                """
            )
        )
    )


def _multiple_current_source_rows(bind: sa.engine.Connection) -> list[sa.Row[tuple[object, ...]]]:
    return list(
        bind.execute(
            sa.text(
                """
                SELECT lead_id, COUNT(*) AS row_count
                FROM lead_source_records
                WHERE is_current = TRUE
                GROUP BY lead_id
                HAVING COUNT(*) > 1
                ORDER BY lead_id
                LIMIT 20
                """
            )
        )
    )


def _format_conflict_rows(rows: list[sa.Row[tuple[object, ...]]]) -> str:
    return "; ".join(", ".join(str(value) for value in row) for row in rows)


def _has_column(bind: sa.engine.Connection, table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(bind)
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def _has_foreign_key(bind: sa.engine.Connection, table_name: str, constraint_name: str) -> bool:
    inspector = sa.inspect(bind)
    return any(
        foreign_key.get("name") == constraint_name
        for foreign_key in inspector.get_foreign_keys(table_name)
    )


def _has_unique_constraint(
    bind: sa.engine.Connection,
    table_name: str,
    constraint_name: str,
) -> bool:
    inspector = sa.inspect(bind)
    return any(
        unique_constraint.get("name") == constraint_name
        for unique_constraint in inspector.get_unique_constraints(table_name)
    )


def _has_index(bind: sa.engine.Connection, table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(bind)
    return any(index.get("name") == index_name for index in inspector.get_indexes(table_name))


def upgrade() -> None:
    bind = None
    if not context.is_offline_mode():
        bind = op.get_bind()
        duplicate_usage_counters = _duplicate_usage_counter_rows(bind)
        if duplicate_usage_counters:
            raise RuntimeError(
                "Cannot apply 0008_db_hardening_integrity because duplicate usage_counters rows "
                "exist for (workspace_id, metric_key, period_start, period_end). Conflicts: "
                f"{_format_conflict_rows(duplicate_usage_counters)}"
            )

        multiple_current_sources = _multiple_current_source_rows(bind)
        if multiple_current_sources:
            raise RuntimeError(
                "Cannot apply 0008_db_hardening_integrity because some leads have multiple "
                "current lead_source_records. Conflicts: "
                f"{_format_conflict_rows(multiple_current_sources)}"
            )

    if bind is None or not _has_column(bind, "lead_source_records", "current_for_lead_id"):
        op.add_column(
            "lead_source_records",
            sa.Column("current_for_lead_id", sa.Integer(), nullable=True),
        )
    op.execute(
        sa.text(
            """
            UPDATE lead_source_records
            SET current_for_lead_id = CASE
                WHEN is_current = TRUE THEN lead_id
                ELSE NULL
            END
            """
        )
    )
    if bind is None or not _has_foreign_key(
        bind,
        "lead_source_records",
        "fk_lead_source_records_current_for_lead_id",
    ):
        op.create_foreign_key(
            "fk_lead_source_records_current_for_lead_id",
            "lead_source_records",
            "leads",
            ["current_for_lead_id"],
            ["id"],
        )
    if bind is None or not _has_unique_constraint(
        bind,
        "lead_source_records",
        "uq_lead_source_records_current_for_lead_id",
    ):
        op.create_unique_constraint(
            "uq_lead_source_records_current_for_lead_id",
            "lead_source_records",
            ["current_for_lead_id"],
        )
    if bind is None or not _has_index(
        bind,
        "lead_source_records",
        "ix_lead_source_records_lead_current_priority",
    ):
        op.create_index(
            "ix_lead_source_records_lead_current_priority",
            "lead_source_records",
            ["lead_id", "is_current", "priority"],
        )

    if bind is None or not _has_unique_constraint(
        bind,
        "usage_counters",
        "uq_usage_counters_workspace_metric_period",
    ):
        op.create_unique_constraint(
            "uq_usage_counters_workspace_metric_period",
            "usage_counters",
            ["workspace_id", "metric_key", "period_start", "period_end"],
        )
    if bind is None or not _has_index(
        bind,
        "usage_counters",
        "ix_usage_counters_workspace_period_end_metric",
    ):
        op.create_index(
            "ix_usage_counters_workspace_period_end_metric",
            "usage_counters",
            ["workspace_id", "period_end", "metric_key"],
        )

    if bind is None or not _has_index(bind, "subscriptions", "ix_subscriptions_workspace_id_id"):
        op.create_index(
            "ix_subscriptions_workspace_id_id",
            "subscriptions",
            ["workspace_id", "id"],
        )
    if bind is None or not _has_index(bind, "invoices", "ix_invoices_workspace_issued_at_id"):
        op.create_index(
            "ix_invoices_workspace_issued_at_id",
            "invoices",
            ["workspace_id", "issued_at", "id"],
        )
    if bind is None or not _has_index(bind, "invoice_items", "ix_invoice_items_invoice_id_id"):
        op.create_index(
            "ix_invoice_items_invoice_id_id",
            "invoice_items",
            ["invoice_id", "id"],
        )
    if bind is None or not _has_index(
        bind,
        "payment_attempts",
        "ix_payment_attempts_invoice_attempted_at_id",
    ):
        op.create_index(
            "ix_payment_attempts_invoice_attempted_at_id",
            "payment_attempts",
            ["invoice_id", "attempted_at", "id"],
        )


def downgrade() -> None:
    op.drop_index("ix_payment_attempts_invoice_attempted_at_id", table_name="payment_attempts")
    op.drop_index("ix_invoice_items_invoice_id_id", table_name="invoice_items")
    op.drop_index("ix_invoices_workspace_issued_at_id", table_name="invoices")
    op.drop_index("ix_subscriptions_workspace_id_id", table_name="subscriptions")
    op.drop_index(
        "ix_usage_counters_workspace_period_end_metric",
        table_name="usage_counters",
    )
    op.drop_constraint(
        "uq_usage_counters_workspace_metric_period",
        "usage_counters",
        type_="unique",
    )
    op.drop_index(
        "ix_lead_source_records_lead_current_priority",
        table_name="lead_source_records",
    )
    op.drop_constraint(
        "uq_lead_source_records_current_for_lead_id",
        "lead_source_records",
        type_="unique",
    )
    op.drop_constraint(
        "fk_lead_source_records_current_for_lead_id",
        "lead_source_records",
        type_="foreignkey",
    )
    op.drop_column("lead_source_records", "current_for_lead_id")
