from __future__ import annotations

from app.core.config import Settings, clear_settings_cache


def test_analysis_runtime_prefers_ollama_and_falls_back_to_openai(monkeypatch) -> None:
    monkeypatch.setenv("AI_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
    monkeypatch.setenv("OLLAMA_MODEL", "llama3.1")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    clear_settings_cache()

    settings = Settings()

    assert settings.analysis_runtime == "ollama"
    assert settings.analysis_fallback_runtime == "openai"


def test_openai_base_url_is_env_configurable(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_BASE_URL", "https://llm-gateway.example.test/v1")
    clear_settings_cache()

    settings = Settings()

    assert settings.openai_base_url == "https://llm-gateway.example.test/v1"


def test_discovery_runtime_is_blocked_without_serpapi_key(monkeypatch) -> None:
    monkeypatch.setenv("SERPAPI_API_KEY", "")
    monkeypatch.setenv("SERPAPI_RUNTIME_MODE", "blocked")
    clear_settings_cache()

    settings = Settings()

    assert settings.discovery_runtime == "blocked"


def test_discovery_engine_list_alias_and_effective_mode(monkeypatch) -> None:
    monkeypatch.setenv("DISCOVERY_ENGINE_LIST", "google_maps_search,google_web")
    monkeypatch.setenv("DISCOVERY_MODE", "multi_engine_multi_query")
    monkeypatch.setenv("DISCOVERY_MULTI_ENGINE_ENABLED", "false")
    clear_settings_cache()

    settings = Settings()

    assert settings.enabled_discovery_engines == ["google_maps_search", "google_web"]
    assert settings.effective_discovery_mode == "multi_query_single_engine"


def test_discovery_kill_switch_forces_single_path(monkeypatch) -> None:
    monkeypatch.setenv("DISCOVERY_KILL_SWITCH", "true")
    monkeypatch.setenv("DISCOVERY_MODE", "multi_engine_multi_query")
    clear_settings_cache()

    settings = Settings()

    assert settings.effective_discovery_mode == "single_path"


def test_production_rejects_local_default_admin_password(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SECRET", "x" * 40)
    monkeypatch.setenv("WEB_ORIGINS", "https://example.com")
    monkeypatch.setenv("SERPAPI_RUNTIME_MODE", "live")
    monkeypatch.setenv("SERPAPI_API_KEY", "serp-key")
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    monkeypatch.setenv(
        "DEFAULT_ADMIN_PASSWORD",
        "local-dev-admin-password-rotate-before-sharing",
    )
    clear_settings_cache()

    try:
        Settings()
        raise AssertionError(
            "Settings() should have raised for local development default admin password."
        )
    except ValueError as exc:
        assert "local development default value" in str(exc)


def test_production_rejects_stub_ai_provider(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SECRET", "x" * 40)
    monkeypatch.setenv("WEB_ORIGINS", "https://example.com")
    monkeypatch.setenv("SERPAPI_RUNTIME_MODE", "live")
    monkeypatch.setenv("SERPAPI_API_KEY", "serp-key")
    monkeypatch.setenv("DEFAULT_ADMIN_PASSWORD", "strong-password-1234")
    monkeypatch.setenv("AI_PROVIDER", "stub")
    clear_settings_cache()

    try:
        Settings()
        raise AssertionError("Settings() should have raised for AI_PROVIDER=stub in production.")
    except ValueError as exc:
        assert "AI_PROVIDER=stub" in str(exc)


def test_demo_discovery_mode_does_not_warn_about_missing_serpapi_key(monkeypatch) -> None:
    monkeypatch.setenv("SERPAPI_RUNTIME_MODE", "demo")
    monkeypatch.setenv("SERPAPI_API_KEY", "")
    clear_settings_cache()

    settings = Settings()

    assert settings.discovery_runtime == "demo"
    assert not any("SERPAPI_API_KEY" in warning for warning in settings.runtime_warnings)
