from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"

DiscoveryRuntime = Literal["live", "demo", "stub", "blocked"]
AnalysisRuntime = Literal["ollama", "openai", "demo", "blocked"]
AIProviderPreference = Literal["ollama", "openai", "auto", "stub"]
DiscoveryMode = Literal["single_path", "multi_query_single_engine", "multi_engine_multi_query"]


class Settings(BaseSettings):
    app_name: str = "LeadScope AI API"
    app_env: str = "development"
    api_v1_prefix: str = "/api/v1"

    database_url: str = "mysql+pymysql://prospectiq:prospectiq@127.0.0.1:3306/prospectiq"

    jwt_secret: str = "<replace-me>"
    jwt_expire_minutes: int = 120

    web_origin: str = "http://localhost:5173"
    web_origins: Annotated[list[str], NoDecode] = Field(default_factory=list)

    sql_echo: bool = False
    log_level: str = "INFO"
    enable_db_healthcheck: bool = True
    enable_request_logging: bool = True
    enable_api_docs: bool = False

    default_admin_email: str = "admin@prospectiq.dev"
    default_admin_password: str = "ChangeMe123!"
    default_admin_name: str = "LeadScope AI Admin"
    default_workspace_public_id: str = "ws_default"
    default_workspace_name: str = "Default Workspace"

    # External providers: NEVER hardcode real secrets here.
    serpapi_api_key: str = ""
    serpapi_base_url: str = "https://serpapi.com/search.json"

    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"
    openai_base_url: str = "https://api.openai.com/v1"

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"
    ai_provider: AIProviderPreference = Field(
        default="ollama",
        validation_alias=AliasChoices("AI_PROVIDER"),
    )

    # Runtime control:
    # - live: use SerpAPI
    # - demo: explicit demo mode
    # - stub: deterministic test mode
    # - blocked: production-safe block
    discovery_runtime_override: DiscoveryRuntime | None = Field(
        default=None,
        validation_alias=AliasChoices("SERPAPI_RUNTIME_MODE", "DISCOVERY_RUNTIME_OVERRIDE"),
    )
    discovery_kill_switch: bool = False
    discovery_mode: DiscoveryMode = "multi_engine_multi_query"
    discovery_multi_engine_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices("DISCOVERY_MULTI_ENGINE_ENABLED"),
    )
    discovery_enabled_engines: str = Field(
        default="google_maps_search,google_web",
        validation_alias=AliasChoices("DISCOVERY_ENABLED_ENGINES", "DISCOVERY_ENGINE_LIST"),
    )
    # LLM-native web search tool (passed as a function/tool to OpenAI-compat providers).
    # When enabled, the assistant can call SerpAPI on demand via an LLM tool_call.
    enable_llm_web_search: bool = Field(
        default=True,
        validation_alias=AliasChoices("ENABLE_LLM_WEB_SEARCH"),
    )
    llm_web_search_max_results: int = Field(
        default=5,
        ge=1,
        le=20,
        validation_alias=AliasChoices("LLM_WEB_SEARCH_MAX_RESULTS"),
    )
    discovery_max_concurrency: int = Field(default=4, ge=1, le=32)
    discovery_max_calls_per_job: int = Field(default=24, ge=1, le=200)
    discovery_max_candidates_after_merge: int = Field(default=100, ge=1, le=2000)
    discovery_max_enrichments_per_job: int = Field(default=20, ge=0, le=500)
    discovery_global_job_deadline_seconds: int = Field(default=300, ge=1, le=3600)
    discovery_bilingual_expansion_enabled: bool = True
    discovery_circuit_breaker_failure_threshold: int = Field(default=3, ge=1, le=20)
    discovery_circuit_breaker_cooldown_seconds: int = Field(default=60, ge=1, le=3600)

    # Billing simulation is a developer-only tool; disabled by default.
    # Set ENABLE_BILLING_SIMULATION=true only in non-production environments.
    enable_billing_simulation: bool = False

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        normalized = value.lower()
        if not normalized.startswith(("mysql://", "mysql+", "mariadb://", "mariadb+")):
            raise ValueError("DATABASE_URL must use a MySQL or MariaDB SQLAlchemy dialect.")
        return value

    @field_validator("web_origin")
    @classmethod
    def validate_web_origin(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("WEB_ORIGIN must not be empty.")
        return stripped.rstrip("/")

    @field_validator("web_origins", mode="before")
    @classmethod
    def validate_web_origins(cls, value: object) -> list[str]:
        if value in (None, ""):
            return []

        if isinstance(value, str):
            return [item.strip().rstrip("/") for item in value.split(",") if item.strip()]

        if isinstance(value, list):
            return [str(item).strip().rstrip("/") for item in value if str(item).strip()]

        raise ValueError("WEB_ORIGINS must be a comma-separated string or list.")

    @model_validator(mode="after")
    def validate_production_config(self) -> "Settings":
        if self.app_env.lower() != "production":
            return self

        if self.jwt_secret == "<replace-me>":
            raise ValueError(
                "APP_ENV=production requires JWT_SECRET to be set to a non-placeholder value."
            )

        if len(self.jwt_secret.strip()) < 32:
            raise ValueError(
                "APP_ENV=production requires JWT_SECRET to be at least 32 characters long."
            )

        if self.default_admin_password == "ChangeMe123!":
            raise ValueError(
                "APP_ENV=production requires DEFAULT_ADMIN_PASSWORD to be changed from the default value."
            )
        if self.default_admin_password == "local-dev-admin-password-rotate-before-sharing":
            raise ValueError(
                "APP_ENV=production requires DEFAULT_ADMIN_PASSWORD to be changed from the local development default value."
            )

        if len(self.default_admin_password.strip()) < 12:
            raise ValueError(
                "APP_ENV=production requires DEFAULT_ADMIN_PASSWORD to be at least 12 characters long."
            )

        if not self.web_origins:
            raise ValueError(
                "APP_ENV=production requires WEB_ORIGINS to be explicitly configured."
            )

        if not self.has_serpapi_configured:
            raise ValueError(
                "APP_ENV=production requires SERPAPI_API_KEY to be set for live lead discovery."
            )

        if not (self.has_openai_configured or self.has_ollama_configured):
            raise ValueError(
                "APP_ENV=production requires either OPENAI_API_KEY or OLLAMA_BASE_URL + OLLAMA_MODEL."
            )

        if self.discovery_runtime == "demo":
            raise ValueError(
                "APP_ENV=production must not run with SERPAPI_RUNTIME_MODE=demo."
            )

        if self.discovery_runtime == "stub":
            raise ValueError(
                "APP_ENV=production must not run with SERPAPI_RUNTIME_MODE=stub."
            )
        if self.ai_provider == "stub":
            raise ValueError(
                "APP_ENV=production must not run with AI_PROVIDER=stub."
            )

        return self

    @property
    def normalized_app_env(self) -> str:
        return self.app_env.strip().lower()

    @property
    def is_development(self) -> bool:
        return self.normalized_app_env in {"local", "dev", "development"}

    @property
    def is_testing(self) -> bool:
        return self.normalized_app_env in {"test", "testing", "ci"}

    @property
    def is_production(self) -> bool:
        return self.normalized_app_env == "production"

    @property
    def has_serpapi_configured(self) -> bool:
        return bool(self.serpapi_api_key.strip())

    @property
    def has_openai_configured(self) -> bool:
        return bool(self.openai_api_key.strip())

    @property
    def has_ollama_configured(self) -> bool:
        return bool(self.ollama_base_url.strip() and self.ollama_model.strip())

    @property
    def discovery_runtime(self) -> DiscoveryRuntime:
        if self.discovery_runtime_override:
            return self.discovery_runtime_override

        if self.is_testing:
            return "stub"

        if self.has_serpapi_configured:
            return "live"

        return "blocked"

    @property
    def runtime_warnings(self) -> list[str]:
        warnings: list[str] = []

        if self.discovery_runtime == "stub":
            warnings.append("Discovery is running in stub mode for tests only.")

        if self.discovery_runtime == "blocked":
            warnings.append(
                "Discovery runtime is blocked because no live SerpAPI key is configured."
            )
        if self.discovery_kill_switch:
            warnings.append("Discovery kill switch is enabled; discovery always runs in single_path mode.")
        if (
            self.discovery_mode == "multi_engine_multi_query"
            and not self.discovery_multi_engine_enabled
        ):
            warnings.append(
                "DISCOVERY_MULTI_ENGINE_ENABLED=false downgrades mode to multi_query_single_engine."
            )

        if self.jwt_secret in {"<replace-me>", ""}:
            warnings.append(
                "JWT_SECRET is set to a placeholder value. Rotate it before sharing this environment."
            )

        if self.discovery_runtime in {"live", "blocked"} and self.serpapi_api_key in {"<replace-me>", ""}:
            warnings.append(
                "SERPAPI_API_KEY is not configured or is a placeholder. Live discovery will not work."
            )

        if self.default_admin_password in {
            "ChangeMe123!",
            "local-dev-admin-password-rotate-before-sharing",
        }:
            warnings.append(
                "DEFAULT_ADMIN_PASSWORD is set to a default value. Rotate it before sharing this environment."
            )

        if self.analysis_runtime == "blocked":
            warnings.append(
                "AI runtime is blocked because no configured Ollama or OpenAI provider is available."
            )

        if self.analysis_runtime == "ollama" and not self.has_openai_configured:
            warnings.append(
                "Ollama is the primary AI runtime and no OpenAI fallback key is configured."
            )

        return warnings

    @property
    def serpapi_runtime_mode(self) -> str:
        return self.discovery_runtime

    @property
    def effective_discovery_mode(self) -> DiscoveryMode:
        if self.discovery_kill_switch:
            return "single_path"
        if self.discovery_mode == "multi_engine_multi_query" and not self.discovery_multi_engine_enabled:
            return "multi_query_single_engine"
        return self.discovery_mode

    @property
    def analysis_runtime(self) -> AnalysisRuntime:
        if self.ai_provider == "stub" or self.is_testing:
            return "demo"

        if self.ai_provider == "ollama":
            if self.has_ollama_configured:
                return "ollama"
            if self.has_openai_configured:
                return "openai"
            return "blocked"

        if self.ai_provider == "openai":
            if self.has_openai_configured:
                return "openai"
            if self.has_ollama_configured:
                return "ollama"
            return "blocked"

        if self.has_ollama_configured:
            return "ollama"
        if self.has_openai_configured:
            return "openai"
        return "blocked"

    @property
    def analysis_fallback_runtime(self) -> AnalysisRuntime | None:
        if self.analysis_runtime == "demo":
            return None
        if self.analysis_runtime == "ollama" and self.has_openai_configured:
            return "openai"
        if self.analysis_runtime == "openai" and self.has_ollama_configured:
            return "ollama"
        return None

    @property
    def allow_demo_fallbacks(self) -> bool:
        return self.analysis_runtime == "demo"

    @property
    def billing_simulation_enabled(self) -> bool:
        return self.is_testing or self.enable_billing_simulation

    @property
    def allowed_web_origins(self) -> list[str]:
        origins = list(self.web_origins) if self.web_origins else [self.web_origin]

        if self.is_development:
            expanded: list[str] = []

            for origin in origins:
                expanded.append(origin)

                if "localhost" in origin:
                    expanded.append(origin.replace("localhost", "127.0.0.1"))
                elif "127.0.0.1" in origin:
                    expanded.append(origin.replace("127.0.0.1", "localhost"))

            seen: set[str] = set()
            deduped: list[str] = []

            for origin in expanded:
                if origin not in seen:
                    seen.add(origin)
                    deduped.append(origin)

            return deduped

        return origins

    @property
    def enabled_discovery_engines(self) -> list[str]:
        values = [item.strip() for item in self.discovery_enabled_engines.split(",")]
        return [item for item in values if item]


@lru_cache
def get_settings() -> Settings:
    return Settings()


def clear_settings_cache() -> None:
    get_settings.cache_clear()
