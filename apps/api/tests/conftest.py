from __future__ import annotations

import pytest

import app.core.rate_limit as _rl
from app.core.config import clear_settings_cache


@pytest.fixture(autouse=True)
def _stable_settings_defaults(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("JWT_SECRET", "test-jwt-secret-with-at-least-32-bytes")
    # Enable billing simulation in tests so simulation endpoints are reachable
    monkeypatch.setenv("ENABLE_BILLING_SIMULATION", "true")
    clear_settings_cache()
    yield
    clear_settings_cache()


@pytest.fixture(autouse=True)
def _disable_rate_limiter():
    """Disable the in-memory rate limiter during tests to prevent cross-test bleed."""
    _rl._enabled = False
    _rl._windows.clear()
    yield
    _rl._windows.clear()
    _rl._enabled = True
