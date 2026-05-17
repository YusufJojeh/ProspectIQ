"""Inspect database integrity and growth hotspots with dry-run defaults."""

from __future__ import annotations

# ruff: noqa: E402
import argparse
import json
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.core.config import clear_settings_cache, get_settings


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run a dry-run database maintenance audit for duplicate logical counters, "
            "lead source integrity, and growth-prone tables."
        )
    )
    parser.add_argument(
        "--database-url",
        help="Optional SQLAlchemy database URL. Defaults to DATABASE_URL from app settings.",
    )
    parser.add_argument(
        "--large-table-threshold",
        type=int,
        default=1000,
        help="Flag tables at or above this row count. Defaults to 1000.",
    )
    parser.add_argument(
        "--apply-current-marker-repair",
        action="store_true",
        help=(
            "Repair lead_source_records.current_for_lead_id so current rows point to lead_id and "
            "non-current rows are NULL. No rows are deleted."
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the report as JSON.",
    )
    return parser.parse_args(argv)


def resolve_database_url(explicit_database_url: str | None) -> str:
    if explicit_database_url:
        return explicit_database_url
    clear_settings_cache()
    return get_settings().database_url


def create_db_engine(database_url: str) -> Engine:
    return create_engine(database_url, pool_pre_ping=True, future=True)


def collect_report(engine: Engine, *, large_table_threshold: int) -> dict[str, Any]:
    duplicate_usage_counters_sql = text(
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
    multiple_current_sources_sql = text(
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
    current_marker_mismatches_sql = text(
        """
        SELECT id, lead_id, current_for_lead_id, is_current
        FROM lead_source_records
        WHERE
            (
                is_current = TRUE
                AND (current_for_lead_id IS NULL OR current_for_lead_id != lead_id)
            )
            OR
            (is_current = FALSE AND current_for_lead_id IS NOT NULL)
        ORDER BY id
        LIMIT 20
        """
    )

    growth_tables = [
        "provider_raw_payloads",
        "provider_normalized_facts",
        "ai_analysis_snapshots",
        "chat_messages",
        "audit_logs",
        "outreach_messages",
    ]

    report: dict[str, Any] = {
        "duplicate_usage_counters": [],
        "multiple_current_lead_sources": [],
        "current_marker_mismatches": [],
        "table_counts": {},
        "large_tables": {},
    }

    with engine.connect() as connection:
        inspector = inspect(connection)
        report["duplicate_usage_counters"] = [
            dict(row) for row in connection.execute(duplicate_usage_counters_sql).mappings()
        ]
        report["multiple_current_lead_sources"] = [
            dict(row) for row in connection.execute(multiple_current_sources_sql).mappings()
        ]
        report["current_marker_mismatches"] = [
            dict(row) for row in connection.execute(current_marker_mismatches_sql).mappings()
        ]

        for table_name in growth_tables:
            if not inspector.has_table(table_name):
                report["table_counts"][table_name] = 0
                continue
            row_count = int(
                connection.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar() or 0
            )
            report["table_counts"][table_name] = row_count
            if row_count >= large_table_threshold:
                report["large_tables"][table_name] = row_count

    return report


def apply_current_marker_repair(engine: Engine) -> int:
    with engine.begin() as connection:
        result = connection.execute(
            text(
                """
                UPDATE lead_source_records
                SET current_for_lead_id = CASE
                    WHEN is_current = TRUE THEN lead_id
                    ELSE NULL
                END
                WHERE
                    (
                        is_current = TRUE
                        AND (current_for_lead_id IS NULL OR current_for_lead_id != lead_id)
                    )
                    OR
                    (is_current = FALSE AND current_for_lead_id IS NOT NULL)
                """
            )
        )
    return int(result.rowcount or 0)


def render_text_report(
    report: dict[str, Any],
    *,
    large_table_threshold: int,
    repaired_rows: int | None,
) -> str:
    lines = [
        "Database maintenance audit",
        "Mode: dry-run" if repaired_rows is None else "Mode: repair + audit",
        f"Large table threshold: {large_table_threshold}",
        "",
        f"Duplicate usage_counters groups: {len(report['duplicate_usage_counters'])}",
        f"Multiple current lead_source_records groups: {len(report['multiple_current_lead_sources'])}",
        f"Lead source marker mismatches: {len(report['current_marker_mismatches'])}",
        f"Large tables: {len(report['large_tables'])}",
    ]
    if repaired_rows is not None:
        lines.append(f"Current-marker rows repaired: {repaired_rows}")

    def append_rows(title: str, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        lines.append("")
        lines.append(title)
        for row in rows:
            lines.append(f"- {json.dumps(row, default=str, ensure_ascii=True, sort_keys=True)}")

    append_rows("Duplicate usage_counters samples", report["duplicate_usage_counters"])
    append_rows(
        "Multiple current lead_source_records samples",
        report["multiple_current_lead_sources"],
    )
    append_rows("Lead source marker mismatch samples", report["current_marker_mismatches"])

    if report["large_tables"]:
        lines.append("")
        lines.append("Large table counts")
        for table_name, row_count in sorted(report["large_tables"].items()):
            lines.append(f"- {table_name}: {row_count}")

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    database_url = resolve_database_url(args.database_url)
    engine = create_db_engine(database_url)

    repaired_rows: int | None = None
    if args.apply_current_marker_repair:
        repaired_rows = apply_current_marker_repair(engine)

    report = collect_report(engine, large_table_threshold=args.large_table_threshold)
    if args.json:
        payload = {
            "mode": "repair" if repaired_rows is not None else "dry-run",
            "large_table_threshold": args.large_table_threshold,
            "repaired_rows": repaired_rows,
            "report": report,
        }
        print(json.dumps(payload, default=str, ensure_ascii=True, sort_keys=True, indent=2))
    else:
        print(
            render_text_report(
                report,
                large_table_threshold=args.large_table_threshold,
                repaired_rows=repaired_rows,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
