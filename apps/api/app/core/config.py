from functools import lru_cache

from pydantic import AnyHttpUrl, Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "ProspectIQ API"
    app_env: str = "development"
    api_v1_prefix: str = "/api/v1"
    database_url: str = "mysql+pymysql://prospectiq:prospectiq@127.0.0.1:3306/prospectiq"
    jwt_secret: str = "<replace-me>"
    jwt_expire_minutes: int = 120
    web_origin: AnyHttpUrl = Field(default="http://localhost:5173")
    sql_echo: bool = False
    log_level: str = "INFO"
    enable_db_healthcheck: bool = True
    enable_request_logging: bool = True
    default_admin_email: str = "admin@prospectiq.local"
    default_admin_password: str = "ChangeMe123!"
    default_admin_name: str = "ProspectIQ Admin"
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

    @computed_field
    @property
    def is_development(self) -> bool:
        return self.app_env.lower() == "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()
