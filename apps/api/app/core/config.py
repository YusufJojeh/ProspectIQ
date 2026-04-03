from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


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
    default_admin_email: str = "admin@prospectiq.dev"
    default_admin_password: str = "ChangeMe123!"
    default_admin_name: str = "LeadScope AI Admin"
    default_workspace_public_id: str = "ws_default"
    default_workspace_name: str = "Default Workspace"

    serpapi_api_key: str = "<replace-me>"
    serpapi_base_url: str = "https://serpapi.com/search.json"

    ai_provider: str = "stub"
    openai_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"

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
    def is_development(self) -> bool:
        return self.app_env.lower() == "development"

    @property
    def runtime_warnings(self) -> list[str]:
        warnings: list[str] = []
        if self.jwt_secret == "<replace-me>":
            warnings.append("JWT_SECRET is still set to the placeholder value.")
        if self.serpapi_api_key == "<replace-me>":
            warnings.append("SERPAPI_API_KEY is still set to the placeholder value.")
        if self.default_admin_password == "ChangeMe123!":
            warnings.append("DEFAULT_ADMIN_PASSWORD is still using the local-development default.")
        if not self.web_origins and "127.0.0.1" not in self.allowed_web_origins:
            warnings.append(
                "WEB_ORIGINS is not set; only the primary WEB_ORIGIN will be allowed outside development."
            )
        return warnings


@lru_cache
def get_settings() -> Settings:
    return Settings()


def clear_settings_cache() -> None:
    get_settings.cache_clear()
