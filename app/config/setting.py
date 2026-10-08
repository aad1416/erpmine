import json
from typing import Annotated, List

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

EMBEDDING_PROVIDERS = {
    "openai",
    "chroma",
    "default",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        extra="ignore",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    access_token_secret_key: str | None = None
    access_token_algorithm: str = "HS256"
    access_token_expire_minutes: int
    database_url: str | None = None
    lyndom_db_url: str | None = None
    # Postgres statement_timeout applied to every Lyndom connection, so one
    # runaway LLM-generated query cannot stall a chat or degrade the shared ERP DB.
    LYNDOM_SQL_TIMEOUT_MS: int = 15000
    vector_store_path: str | None = None
    file_storage_path: str | None = None
    allowed_file_types: Annotated[List[str], NoDecode]
    max_file_size_mb: int

    # Seed scheduler
    SEED_SCHEDULER_ENABLED: bool = True
    SEED_INTERVAL_MINUTES: int = 20
    SEED_LOCK_FILE: str = "/tmp/ut-ai-seed.lock"

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PASSWORD: str | None = None
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    # Speech-to-Text (STT)
    MAX_AUDIO_SIZE_MB: int = 25
    MAX_AUDIO_DURATION_SECONDS: int = 600

    # Embeddings
    embedding_provider: str | None = None
    embedding_model_name: str | None = None
    embedding_batch_size: int = 64

    # LLM API Keys
    OPENAI_API_KEY: str | None = None
    ANTHROPIC_API_KEY: str | None = None
    GOOGLE_API_KEY: str | None = None
    GROK_API_KEY: str | None = None
    TAVILY_API_KEY: str | None = None

    # LlamaParse
    LLAMA_PARSE_API_KEY: str | None = Field(
        default=None,
        validation_alias=AliasChoices("LLAMA_PARSE_API_KEY", "LLAMA_CLOUD_API_KEY"),
    )
    LLAMA_PARSE_LANGUAGE: str = "en"
    LLAMA_PARSE_CONFIG_PROFILE: str = "cost_efficient"
    LLAMA_PARSE_VERSION: str | None = "latest"

    # Parser backend: "llama" (LlamaParse cloud API) | "fast" (pymupdf4llm local)
    DOCUMENT_PARSER_BACKEND: str = "fast"

    # Tools: make-post HTML generation
    MAKE_POST_MODEL: str = "gpt-4o"

    # Tools: compare-invoice markdown comparison
    COMPARE_INVOICE_MODEL: str = "gpt-4o"

    # Tools: report generation
    REPORT_MODEL: str = "gpt-4o"

    # Tools: field service ticket summary
    FIELD_SERVICE_TICKET_SUMMARY_MODEL: str = "gpt-4o"

    # Tools: unit root cause analysis
    UNIT_RCA_MODEL: str = "gpt-4o"

    # Chunking settings
    MARKDOWN_CHUNKER_BACKEND: str = "llamaindex"
    TEXT_CHUNK_SIZE: int = 400
    TEXT_CHUNK_OVERLAP: int = 100
    TABLE_MAX_ROWS: int = 30
    TABLE_ROW_OVERLAP: int = 4
    MIN_SECTION_TOKENS: int = 200
    RAG_SIMILARITY_THRESHOLD: float = 0.25
    VECTOR_STORE_DISTANCE_SPACE: str = "cosine"

    # Database RAG
    DB_RAG_ENABLED: bool = True
    DB_RAG_FAST_MODEL: str = "gpt-5.4-nano"
    DB_RAG_QUERY_GEN_MODEL: str = "gpt-5.4-mini"
    DB_RAG_TABLE_DOCS_PATH: str = "docs/database/table-docs"
    DB_RAG_TOP_K: int | None = 20
    DB_RAG_RRF_ALPHA: float = 0.5
    DB_RAG_SIMILARITY_THRESHOLD: float = 0.25
    DB_RAG_MAX_ROWS: int | None = 200
    DB_RAG_USE_LLM_TABLE_SELECTION: bool = False
    DB_RAG_SQL_MAX_SCHEMA_TABLES: int = 22

    # OpenAI Agents SDK (feature chat tools path). When false, trace export to OpenAI is disabled.
    CHAT_AGENT_SDK_TRACING: bool = False

    # Root logging level for the app's own loggers. Uvicorn only configures its own
    # loggers, so without this every logging.getLogger(__name__) in app.* falls back to
    # the WARNING-level "last resort" handler and all INFO output is silently dropped.
    LOG_LEVEL: str = "INFO"

    # AI Support Ticket System (app/support/) — see app/support/10-implementation-plan.md
    SUPPORT_ENABLED: bool = True
    SUPPORT_LOCK_FILE: str = "/tmp/ut-ai-support.lock"

    SUPPORT_TASK_MAX_RETRIES: int = 3
    SUPPORT_TASK_HEARTBEAT_TIMEOUT_SECONDS: int = 120
    # The ingestion worker runs at once when the message sink writes a task; this is how
    # often it runs anyway, for retried, reclaimed and other tasks nobody woke it for.
    SUPPORT_WORKER_FALLBACK_INTERVAL_SECONDS: int = 30
    SUPPORT_RETENTION_DAYS: int = 7
    SUPPORT_QUESTION_ROUND_CAP: int = 5
    SUPPORT_SERIAL_CORRECTION_CAP: int = 3
    SUPPORT_LOG_SYNC_RETRY_INTERVAL_SECONDS: int = 60
    SUPPORT_DECISION_MODEL: str = "gpt-4o"
    # Fernet key that encrypts Mailbox Connection credentials in the database (see
    # app/support/adapter/credentials.py). Deliberately no default: unset, reading or
    # writing a credential raises instead of using a key that lives in code.
    SUPPORT_CREDENTIALS_KEY: str | None = None

    # Mailbox Connections (addresses and credentials) live in each Mailbox Adapter's
    # table, not here: scripts/seed_support_mailboxes.py copies them in from the
    # environment. Each adapter's own settings are SUPPORT_<ADAPTER>_* (its settings.py).

    # TEST ONLY — remove once Lyndom recognizes real support inbox addresses as
    # stores. When set, requests whose receivingInboxAddress equals FROM get TO
    # substituted instead, so the create-ticket flow can be validated against a
    # store Lyndom already knows. Both unset = no-op (default/production).
    SUPPORT_TEST_RECEIVING_INBOX_OVERRIDE_FROM: str | None = None
    SUPPORT_TEST_RECEIVING_INBOX_OVERRIDE_TO: str | None = None

    # Field Service Ticket API (Ali's panel — see app/support/04-ticket-api-contracts.md)
    TICKET_API_BASE_URL: str | None = "https://lyndom.com/api"
    TICKET_API_BEARER_TOKEN: str | None = None

    @field_validator("allowed_file_types", mode="before")
    @classmethod
    def _split_allowed_file_types(cls, value: object) -> List[str]:
        if isinstance(value, str):
            trimmed = value.strip()
            if trimmed.startswith("[") and trimmed.endswith("]"):
                try:
                    parsed = json.loads(trimmed)
                except json.JSONDecodeError:
                    parsed = None
                if isinstance(parsed, list):
                    return [str(item).strip() for item in parsed if str(item).strip()]
            return [item.strip() for item in trimmed.split(",") if item.strip()]
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if value is None:
            return []
        return value

    @field_validator("embedding_provider", mode="before")
    @classmethod
    def _require_embedding_provider(cls, value: object) -> str:
        if value is None:
            raise ValueError("EMBEDDING_PROVIDER must be set")
        if isinstance(value, str):
            cleaned = value.strip().lower()
            if not cleaned:
                raise ValueError("EMBEDDING_PROVIDER must be set")
            if cleaned not in EMBEDDING_PROVIDERS:
                raise ValueError(
                    "EMBEDDING_PROVIDER must be one of: "
                    f"{', '.join(sorted(EMBEDDING_PROVIDERS))}"
                )
            return cleaned
        raise ValueError("EMBEDDING_PROVIDER must be a string")

    @field_validator("LLAMA_PARSE_CONFIG_PROFILE", mode="before")
    @classmethod
    def _validate_llama_parse_profile(cls, value: object) -> str:
        if value is None:
            return "cost_efficient"
        if isinstance(value, str):
            cleaned = value.strip().lower().replace("-", "_")
            if cleaned == "cost_effective":
                return "cost_efficient"
            if cleaned in {"agentic", "cost_efficient"}:
                return cleaned
        raise ValueError(
            "LLAMA_PARSE_CONFIG_PROFILE must be 'agentic' or 'cost_efficient'"
        )

    @field_validator("MARKDOWN_CHUNKER_BACKEND", mode="before")
    @classmethod
    def _validate_markdown_chunker_backend(cls, value: object) -> str:
        if value is None:
            return "custom"
        if isinstance(value, str):
            cleaned = value.strip().lower()
            if cleaned in {"custom", "llamaindex"}:
                return cleaned
        raise ValueError("MARKDOWN_CHUNKER_BACKEND must be 'custom' or 'llamaindex'")

    @field_validator("DOCUMENT_PARSER_BACKEND", mode="before")
    @classmethod
    def _validate_document_parser_backend(cls, value: object) -> str:
        if value is None:
            return "fast"
        if isinstance(value, str):
            cleaned = value.strip().lower()
            if cleaned in {"llama", "fast"}:
                return cleaned
        raise ValueError("DOCUMENT_PARSER_BACKEND must be 'llama' or 'fast'")

    @field_validator("DB_RAG_TOP_K", mode="before")
    @classmethod
    def _validate_db_rag_top_k(cls, value: object) -> int | None:
        if value is None:
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            cleaned = value.strip().lower()
            if cleaned in {"", "null", "none"}:
                return None
            try:
                parsed = int(cleaned)
                if parsed < 1:
                    raise ValueError("DB_RAG_TOP_K must be a positive integer or null")
                return parsed
            except ValueError:
                pass
        raise ValueError("DB_RAG_TOP_K must be a positive integer or null")

    @field_validator("DB_RAG_MAX_ROWS", mode="before")
    @classmethod
    def _validate_db_rag_max_rows(cls, value: object) -> int | None:
        if value is None:
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            cleaned = value.strip().lower()
            if cleaned in {"", "null", "none"}:
                return None
            try:
                parsed = int(cleaned)
                if parsed < 1:
                    raise ValueError(
                        "DB_RAG_MAX_ROWS must be a positive integer or null"
                    )
                return parsed
            except ValueError:
                pass
        raise ValueError("DB_RAG_MAX_ROWS must be a positive integer or null")


settings = Settings()
