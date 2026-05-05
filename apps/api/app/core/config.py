from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


DiscoveryRuntime = Literal["live", "demo", "stub", "blocked"]


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

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"

    # Runtime control:
    # - live: use SerpAPI
    # - demo: local/demo mode
    # - stub: deterministic test mode
    # - blocked: production-safe block
    discovery_runtime_override: DiscoveryRuntime | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
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
                "APP_ENV=production must not run with DISCOVERY_RUNTIME_OVERRIDE=demo."
            )

        if self.discovery_runtime == "stub":
            raise ValueError(
                "APP_ENV=production must not run with DISCOVERY_RUNTIME_OVERRIDE=stub."
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

        if self.is_development:
            return "demo"

        return "blocked"

    @property
    def runtime_warnings(self) -> list[str]:
        warnings: list[str] = []

        if self.discovery_runtime in {"demo", "stub"}:
            warnings.append(
                "Discovery is not using a live provider. Search jobs may use demo/stub discovery only if the worker supports it."
            )

        if self.discovery_runtime == "blocked":
            warnings.append(
                "Discovery runtime is blocked because no live provider key is configured."
            )

        # Surface placeholder credential warnings for operators
        if self.jwt_secret in {"<replace-me>", ""}:
            warnings.append(
                "JWT_SECRET is set to a placeholder value. Rotate it before sharing this environment."
            )

        if self.serpapi_api_key in {"<replace-me>", ""}:
            warnings.append(
                "SERPAPI_API_KEY is not configured or is a placeholder. Live discovery will not work."
            )

        if self.default_admin_password in {"ChangeMe123!", "local-dev-admin-password-rotate-before-sharing"}:
            warnings.append(
                "DEFAULT_ADMIN_PASSWORD is set to a default value. Rotate it before sharing this environment."
            )

        return warnings

    @property
    def serpapi_runtime_mode(self) -> str:
        """Discovery runtime mode label for admin API display."""
        return self.discovery_runtime

    @property
    def analysis_runtime(self) -> str:
        """LLM provider mode for AI analysis and assistant.
        Returns: openai | ollama | demo | blocked
        """
        if self.discovery_runtime_override == "blocked":
            return "blocked"
        if self.is_testing:
            return "demo"
        if self.has_openai_configured:
            return "openai"
        if self.has_ollama_configured:
            return "ollama"
        if self.is_development:
            return "demo"
        return "blocked"

    @property
    def allow_demo_fallbacks(self) -> bool:
        """Whether demo/fallback AI responses are permitted."""
        return self.analysis_runtime in {"demo"} or self.is_development or self.is_testing

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


@lru_cache
def get_settings() -> Settings:
    return Settings()


def clear_settings_cache() -> None:
    get_settings.cache_clear()
