"""Verify DATABASE_URL connectivity (run from apps/api with dependencies installed)."""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    # Allow `python scripts/check_database_connection.py` without installing as a package.
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from sqlalchemy import create_engine, text

    from app.core.config import clear_settings_cache, get_settings

    clear_settings_cache()
    settings = get_settings()
    try:
        engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        print(f"Database connection failed: {exc}", file=sys.stderr)
        return 1
    print("Database connection OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
