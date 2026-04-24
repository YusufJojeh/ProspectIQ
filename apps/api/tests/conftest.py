from __future__ import annotations

import pytest

from app.core.config import clear_settings_cache


@pytest.fixture(autouse=True)
def _stable_settings_defaults(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("JWT_SECRET", "test-jwt-secret-with-at-least-32-bytes")
    clear_settings_cache()
    yield
    clear_settings_cache()
