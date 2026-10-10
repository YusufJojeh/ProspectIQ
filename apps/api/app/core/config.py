from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"

DiscoveryRuntime = Literal["live", "demo", "stub", "blocked"]
AnalysisRuntime = Literal["ollama", "openai", "demo", "blocked"]
AIProviderPreference = Literal["ollama", "openai", "auto", "stub"]
ResearchAgentRuntime = Literal["openai", "stub", "blocked"]
AgentRuntimeMode = Literal["openai", "stub", "blocked"]
AgentRuntimeModeSetting = Literal["auto", "openai", "stub", "blocked"]
EmbeddingProviderSetting = Literal["auto", "openai", "local"]
DiscoveryMode = Literal["single_path", "multi_query_single_engine", "multi_engine_multi_query"]
TavilySearchDepth = Literal["basic", "fast", "advanced"]


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

    # Tavily is an optional secondary discovery/validation engine (LLM-grade web
    # search). Unlike SerpAPI it is never production-required: if unconfigured,
    # it is simply excluded from the enabled engine list.
    tavily_api_key: str = ""
    tavily_runtime_mode_override: DiscoveryRuntime | None = Field(
        default=None,
        validation_alias=AliasChoices("TAVILY_RUNTIME_MODE"),
    )
    tavily_live_e2e: bool = Field(default=False, validation_alias=AliasChoices("TAVILY_LIVE_E2E"))
    tavily_max_results: int = Field(
        default=5, ge=1, le=20, validation_alias=AliasChoices("TAVILY_MAX_RESULTS")
    )
    tavily_search_depth: TavilySearchDepth = Field(
        default="basic", validation_alias=AliasChoices("TAVILY_SEARCH_DEPTH")
    )
    tavily_rate_limit_rpm: int = Field(
        default=60, ge=1, le=600, validation_alias=AliasChoices("TAVILY_RATE_LIMIT_RPM")
    )
    tavily_live_max_calls: int = Field(
        default=3, ge=1, le=20, validation_alias=AliasChoices("TAVILY_LIVE_MAX_CALLS")
    )

    # Apify is a deep-extraction/crawling layer, distinct from Tavily/SerpAPI
    # search. It is only ever invoked through a small allowlist of Actor keys
    # (see app.modules.provider_apify.allowlist) resolved to a real Actor ID
    # by this settings object -- callers, including any LLM tool call, can
    # only choose a key, never an arbitrary Actor ID.
    apify_api_token: str = ""
    apify_runtime_mode_override: DiscoveryRuntime | None = Field(
        default=None,
        validation_alias=AliasChoices("APIFY_RUNTIME_MODE"),
    )
    apify_actor_company_website_crawler: str = Field(
        default="apify/website-content-crawler",
        validation_alias=AliasChoices("APIFY_ACTOR_COMPANY_WEBSITE_CRAWLER"),
    )
    apify_actor_business_directory_crawler: str = Field(
        default="",
        validation_alias=AliasChoices("APIFY_ACTOR_BUSINESS_DIRECTORY_CRAWLER"),
    )
    apify_actor_social_public_profile_crawler: str = Field(
        default="",
        validation_alias=AliasChoices("APIFY_ACTOR_SOCIAL_PUBLIC_PROFILE_CRAWLER"),
    )
    apify_actor_reviews_crawler: str = Field(
        default="",
        validation_alias=AliasChoices("APIFY_ACTOR_REVIEWS_CRAWLER"),
    )
    apify_max_dataset_items: int = Field(
        default=20, ge=1, le=200, validation_alias=AliasChoices("APIFY_MAX_DATASET_ITEMS")
    )
    apify_timeout_seconds: int = Field(
        default=90, ge=10, le=300, validation_alias=AliasChoices("APIFY_TIMEOUT_SECONDS")
    )

    # Research depth budget: the maximum number of provider steps
    # ResearchPlanner may schedule per depth tier. Enforced by the planner
    # itself so a deep research request can never silently balloon into
    # calling every configured provider for every lead.
    research_max_steps_quick: int = Field(default=1, ge=1, le=3)
    research_max_steps_standard: int = Field(default=2, ge=1, le=5)
    research_max_steps_deep: int = Field(default=4, ge=1, le=8)

    # Research Agent Loop ("mode": "agentic"): an LLM decides which research
    # tool to call next instead of following ResearchPlanner's fixed steps.
    # It reuses OPENAI_API_KEY (no separate key) and is hard-bounded so a
    # misbehaving or verbose model can never run away with tool calls, live
    # provider spend, or wall-clock time. The LLM only ever names a tool from
    # app.modules.research.tools' fixed registry -- it cannot supply an Apify
    # Actor ID or an arbitrary crawl URL; those stay resolved server-side.
    research_agent_max_tool_calls: int = Field(default=8, ge=1, le=20)
    research_agent_max_external_searches: int = Field(default=5, ge=1, le=10)
    research_agent_max_crawls: int = Field(default=3, ge=1, le=10)
    research_agent_max_sources: int = Field(default=15, ge=1, le=50)
    research_agent_max_runtime_seconds: int = Field(default=60, ge=10, le=300)

    # Delta Intelligence: FactDiffEngine compares each research run's
    # canonical fact snapshot against the previous one. A candidate change
    # below research_delta_min_significance is noise and is dropped; a
    # non-neutral change at or above research_delta_rescore_significance
    # triggers an immediate rescore_lead(). Both are deterministic
    # backend-decided thresholds -- an LLM is never consulted for either.
    research_delta_min_significance: float = Field(default=0.15, ge=0.0, le=1.0)
    research_delta_rescore_significance: float = Field(default=0.4, ge=0.0, le=1.0)

    # Operational Agent Runtime (app.modules.agents): a general-purpose,
    # model-directed tool-calling loop with human-approval-gated write
    # actions. Bounds are enforced in AgentRuntime *before* a tool call or
    # action proposal is ever executed, mirroring research_agent_max_* above
    # but scoped to the whole run rather than one research pass.
    agent_max_steps: int = Field(default=12, ge=1, le=30)
    agent_max_tool_calls: int = Field(default=16, ge=1, le=40)
    agent_max_external_searches: int = Field(default=6, ge=1, le=20)
    agent_max_crawls: int = Field(default=4, ge=1, le=20)
    agent_max_write_proposals: int = Field(default=5, ge=1, le=20)
    agent_max_rag_queries: int = Field(default=8, ge=1, le=40)
    #: External sending (email, WhatsApp, LinkedIn) is OFF by default and must
    #: stay off until a real, audited transport exists. While it is false the
    #: send tools are not even described to the model, the executor refuses
    #: them, and no approved action can execute one.
    external_send_enabled: bool = False

    # --- AI runtime cost control -------------------------------------
    #
    # Prices and model routing are configuration, never code. Both default
    # to empty: with no pricing configured, costs are recorded as UNKNOWN
    # (null) rather than guessed, and with no routing configured every task
    # uses the platform default model.
    provider_pricing_json: str = ""
    agent_model_routing_json: str = ""
    #: Hard ceiling on what one agent run may spend, in micro-USD. Zero
    #: disables the cost ceiling -- which is the right default while pricing
    #: is unconfigured, because a budget computed from unknown costs would
    #: either never trip or trip immediately.
    agent_max_cost_micro_usd: int = Field(default=0, ge=0)
    agent_max_model_calls: int = Field(default=14, ge=1, le=60)
    agent_max_input_tokens: int = Field(default=200_000, ge=1000)
    agent_max_output_tokens: int = Field(default=40_000, ge=500)
    #: How many times a failing model call may be retried on the next
    #: routed candidate. Fallback changes behaviour, so it is bounded and
    #: recorded, never unlimited.
    agent_max_model_fallbacks: int = Field(default=1, ge=0, le=3)
    agent_max_runtime_seconds: int = Field(default=90, ge=10, le=600)
    #: A `running` run whose row has not changed for this long has lost its
    #: background loop (process restart, crash) and is failed by the sweeper.
    #: Never below the runtime budget plus slack; see AgentRuntime.sweep_abandoned_runs.
    agent_stale_run_seconds: int = Field(default=600, ge=120, le=7200)
    agent_max_tool_result_bytes: int = Field(default=16384, ge=1024, le=131072)
    agent_max_sources: int = Field(default=20, ge=1, le=100)
    agent_max_consecutive_tool_failures: int = Field(default=3, ge=1, le=10)
    agent_action_expiry_seconds: int = Field(default=86400, ge=60, le=604800)

    # Live SSE (GET /api/v1/agent/runs/{run_id}/stream). The stream always
    # terminates on its own: either the run reaches a stream-closing state
    # or agent_stream_max_seconds elapses, so a forgotten browser tab can
    # never pin a worker thread indefinitely.
    #: Explicit override for how the agent loop reaches a model. "auto"
    #: (the default) keeps the historical behaviour: stub under APP_ENV=test,
    #: otherwise OpenAI when a key is configured. Setting it explicitly lets
    #: a staging environment pin the stub, and lets the live-provider smoke
    #: exercise the real adapter without changing APP_ENV.
    agent_runtime_mode: AgentRuntimeModeSetting = "auto"
    agent_stream_heartbeat_seconds: int = Field(default=15, ge=1, le=120)
    agent_stream_max_seconds: int = Field(default=300, ge=10, le=3600)
    #: Live-event transport. "inmemory" reaches only subscribers in the
    #: SAME process (correct for one API worker); "redis" fans out across
    #: workers via Redis pub/sub. Persisted AgentEvent rows remain the
    #: replay/audit source of truth either way.
    agent_event_broker: Literal["inmemory", "redis"] = "inmemory"
    redis_url: str | None = None
    agent_event_channel_prefix: str = "prospectiq:agent"
    #: Production escape hatch: acknowledge a single-worker deployment so the
    #: in-memory broker is allowed. Without it production requires Redis, so
    #: multi-worker SSE is never silently degraded.
    agent_event_broker_single_worker: bool = False

    # Sales Knowledge RAG (app.modules.knowledge). "What can WE credibly
    # offer this prospect?" -- distinct from lead research, which stays in
    # the leads/evidence tables and is never embedded into this store.
    # The embedding model is a deployment decision, never a per-request or
    # model-chosen one: mixing vector spaces inside one collection would
    # make similarity meaningless.
    embedding_provider: EmbeddingProviderSetting = "auto"
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = Field(default=1536, ge=8, le=4096)
    embedding_timeout_seconds: float = Field(default=30.0, ge=1.0, le=120.0)
    embedding_fallback_enabled: bool = True
    embedding_batch_size: int = Field(default=32, ge=1, le=256)

    knowledge_chunk_target_chars: int = Field(default=1200, ge=200, le=8000)
    knowledge_chunk_overlap_chars: int = Field(default=150, ge=0, le=2000)
    knowledge_chunk_max_chars: int = Field(default=2400, ge=400, le=16000)
    knowledge_max_document_chars: int = Field(default=400_000, ge=1000, le=5_000_000)
    knowledge_max_chunks_per_document: int = Field(default=400, ge=1, le=5000)
    #: Vector candidates pulled from the (already tenant-filtered) SQL query
    #: before ranking. Bounds the work one search can do.
    knowledge_search_candidate_limit: int = Field(default=400, ge=10, le=5000)
    knowledge_search_default_limit: int = Field(default=5, ge=1, le=50)
    knowledge_search_max_limit: int = Field(default=20, ge=1, le=100)
    knowledge_excerpt_max_chars: int = Field(default=700, ge=100, le=4000)
    #: Weighting between vector similarity and keyword overlap in hybrid
    #: retrieval. Deterministic and configurable -- never model-decided.
    knowledge_hybrid_vector_weight: float = Field(default=0.7, ge=0.0, le=1.0)
    knowledge_min_similarity: float = Field(default=0.05, ge=0.0, le=1.0)
    #: A passage with no lexical overlap with the query at all must clear a
    #: much higher vector bar before it is returned. Hashed or low-dimension
    #: embeddings produce a noise floor of spurious similarity, and a
    #: confidently-cited irrelevant case study is worse for a salesperson
    #: than no result. A genuine synonym match scores far above this.
    knowledge_min_vector_only_similarity: float = Field(default=0.35, ge=0.0, le=1.0)

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
    # Multi-source enrichers run after discovery (comma-separated, empty disables all).
    enrichers_raw: str = Field(
        default="",
        validation_alias=AliasChoices("ENRICHERS"),
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
    discovery_stale_job_seconds: int = Field(default=480, ge=60, le=7200)
    discovery_bilingual_expansion_enabled: bool = True
    # When the primary provider (SerpAPI) yields no candidates — e.g. it is rate
    # limited (HTTP 429) or quota-exhausted — fall back to OpenAI's hosted
    # web-search tool for discovery (requires OPENAI_API_KEY).
    discovery_openai_fallback_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices("DISCOVERY_OPENAI_FALLBACK_ENABLED"),
    )
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
        if not normalized.startswith(("mysql://", "mysql+", "mariadb://", "mariadb+", "sqlite://")):
            raise ValueError(
                "DATABASE_URL must use a MySQL, MariaDB, or SQLite SQLAlchemy dialect."
            )
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

        if self.agent_event_broker == "redis" and not (self.redis_url or "").strip():
            raise ValueError("AGENT_EVENT_BROKER=redis requires REDIS_URL.")
        if self.agent_event_broker == "inmemory" and not self.agent_event_broker_single_worker:
            raise ValueError(
                "APP_ENV=production requires AGENT_EVENT_BROKER=redis (live SSE across API "
                "workers). Set AGENT_EVENT_BROKER_SINGLE_WORKER=true only for a deliberate "
                "single-worker deployment."
            )

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
            raise ValueError("APP_ENV=production requires WEB_ORIGINS to be explicitly configured.")

        if not self.has_serpapi_configured:
            raise ValueError(
                "APP_ENV=production requires SERPAPI_API_KEY to be set for live lead discovery."
            )

        if not (self.has_openai_configured or self.has_ollama_configured):
            raise ValueError(
                "APP_ENV=production requires either OPENAI_API_KEY or OLLAMA_BASE_URL + OLLAMA_MODEL."
            )

        if self.discovery_runtime == "demo":
            raise ValueError("APP_ENV=production must not run with SERPAPI_RUNTIME_MODE=demo.")

        if self.discovery_runtime == "stub":
            raise ValueError("APP_ENV=production must not run with SERPAPI_RUNTIME_MODE=stub.")
        if self.ai_provider == "stub":
            raise ValueError("APP_ENV=production must not run with AI_PROVIDER=stub.")

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
    def has_tavily_configured(self) -> bool:
        value = self.tavily_api_key.strip()
        return bool(value) and value not in {
            "<replace-me>",
            "replace-with-tavily-key",
            "replace-with-live-tavily-key",
        }

    @property
    def tavily_runtime(self) -> DiscoveryRuntime:
        if self.tavily_runtime_mode_override:
            return self.tavily_runtime_mode_override

        if self.is_testing:
            return "stub"

        if self.has_tavily_configured:
            return "live"

        return "blocked"

    @property
    def has_apify_configured(self) -> bool:
        value = self.apify_api_token.strip()
        return bool(value) and value not in {"<replace-me>", "replace-with-apify-token"}

    @property
    def apify_runtime(self) -> DiscoveryRuntime:
        if self.apify_runtime_mode_override:
            return self.apify_runtime_mode_override

        if self.is_testing:
            return "stub"

        if self.has_apify_configured:
            return "live"

        return "blocked"

    @property
    def apify_actor_allowlist(self) -> dict[str, str]:
        """Map allowlisted Actor keys to their configured Apify Actor ID.

        A key with no value configured is omitted, which is how
        ResearchPlanner/ApifyService learn an Actor is allowlisted but not
        available in this deployment.
        """
        mapping = {
            "company_website_crawler": self.apify_actor_company_website_crawler,
            "business_directory_crawler": self.apify_actor_business_directory_crawler,
            "social_public_profile_crawler": self.apify_actor_social_public_profile_crawler,
            "reviews_crawler": self.apify_actor_reviews_crawler,
        }
        return {key: value.strip() for key, value in mapping.items() if value.strip()}

    @property
    def has_openai_configured(self) -> bool:
        return bool(self.openai_api_key.strip())

    @property
    def research_agent_runtime(self) -> ResearchAgentRuntime:
        if self.is_testing:
            return "stub"
        if self.has_openai_configured:
            return "openai"
        return "blocked"

    @property
    def agent_runtime(self) -> AgentRuntimeMode:
        if self.agent_runtime_mode != "auto":
            if self.agent_runtime_mode == "openai" and not self.has_openai_configured:
                return "blocked"
            return self.agent_runtime_mode
        if self.is_testing:
            return "stub"
        if self.has_openai_configured:
            return "openai"
        return "blocked"

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
        if self.agent_runtime == "blocked":
            warnings.append(
                "Agent runtime is blocked because no OPENAI_API_KEY is configured."
            )
        if self.discovery_kill_switch:
            warnings.append(
                "Discovery kill switch is enabled; discovery always runs in single_path mode."
            )
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

        if self.discovery_runtime in {"live", "blocked"} and self.serpapi_api_key in {
            "<replace-me>",
            "",
        }:
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

        if "tavily_web" in self.enabled_discovery_engines and self.tavily_runtime == "blocked":
            warnings.append(
                "DISCOVERY_ENGINE_LIST includes tavily_web but TAVILY_API_KEY is not configured; "
                "it will be skipped."
            )

        if self.tavily_runtime == "live" and not self.has_tavily_configured:
            warnings.append(
                "TAVILY_RUNTIME_MODE=live requires TAVILY_API_KEY; Tavily calls will fail closed."
            )

        if self.apify_runtime == "live" and not self.has_apify_configured:
            warnings.append(
                "APIFY_RUNTIME_MODE=live requires APIFY_API_TOKEN; Apify calls will fail closed."
            )

        if self.apify_runtime != "blocked" and not self.apify_actor_allowlist:
            warnings.append(
                "Apify is enabled but no APIFY_ACTOR_* Actor is configured; "
                "ResearchPlanner will skip all Apify steps."
            )

        if self.research_agent_runtime == "blocked":
            warnings.append(
                "Research agent mode (\"agentic\") is blocked because OPENAI_API_KEY is not "
                "configured; only mode=\"planned\" research will work."
            )

        return warnings

    @property
    def serpapi_runtime_mode(self) -> str:
        return self.discovery_runtime

    @property
    def effective_discovery_mode(self) -> DiscoveryMode:
        if self.discovery_kill_switch:
            return "single_path"
        if (
            self.discovery_mode == "multi_engine_multi_query"
            and not self.discovery_multi_engine_enabled
        ):
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
    def allowed_web_origin_regex(self) -> str | None:
        if not self.is_development:
            return None

        return r"^https?://([a-zA-Z0-9.-]+|\d{1,3}(?:\.\d{1,3}){3})(?::\d+)?$"

    @property
    def enabled_discovery_engines(self) -> list[str]:
        aliases = {
            "serpapi_maps": "google_maps_search",
            "serpapi_map": "google_maps_search",
            "serpapi_web": "google_web",
            "serpapi_search": "google_web",
            "google_maps": "google_maps_search",
            "openai": "openai_web",
            "openai_fallback": "openai_web",
        }
        values = [item.strip() for item in self.discovery_enabled_engines.split(",")]
        normalized: list[str] = []
        for value in values:
            if not value:
                continue
            engine = aliases.get(value, value)
            if engine not in normalized:
                normalized.append(engine)
        return normalized

    @property
    def enrichers(self) -> list[str]:
        values = [item.strip() for item in self.enrichers_raw.split(",")]
        return [item for item in values if item]


@lru_cache
def get_settings() -> Settings:
    return Settings()


def clear_settings_cache() -> None:
    get_settings.cache_clear()
