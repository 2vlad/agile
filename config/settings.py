from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator


class Settings(BaseSettings):
    # Telegram
    telegram_token: str
    admin_user_ids: list[int] = Field(default_factory=list)
    admin_usernames: list[str] = Field(default_factory=list)

    @field_validator("admin_user_ids", mode="before")
    @classmethod
    def parse_admin_ids(cls, v: object) -> list[int]:
        if isinstance(v, str):
            return [int(x.strip()) for x in v.split(",") if x.strip()]
        if isinstance(v, int):
            return [v]
        return v  # type: ignore[return-value]

    @field_validator("admin_usernames", mode="before")
    @classmethod
    def parse_admin_usernames(cls, v: object) -> list[str]:
        if isinstance(v, str):
            return [x.strip().lstrip("@").lower() for x in v.split(",") if x.strip()]
        return v  # type: ignore[return-value]

    # LLM provider
    llm_provider: str = "openai"  # openai | anthropic | yandex | ollama
    llm_api_key: str = ""
    llm_model: str = ""
    llm_base_url: str = ""

    # Embedding provider
    embed_provider: str = "openai"  # openai | yandex | ollama
    embed_api_key: str = ""  # defaults to llm_api_key if empty
    embed_model: str = ""
    embed_dim: int = 1536
    embed_base_url: str = ""

    # Yandex-specific (only when provider=yandex)
    yc_api_key: str = ""
    yc_folder_id: str = ""

    # Database
    database_url: str = "postgresql://bot:bot@localhost:5432/bot"
    db_statement_cache_size: int = 0
    db_ssl_ca: str = ""  # path to CA cert for managed DBs

    # Webhook
    webhook_url: str = ""

    # Bot config
    history_max: int = 20
    history_trim_to: int = 16
    history_ttl_seconds: int = 3600
    auto_index: bool = True

    # Langfuse (optional)
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_base_url: str = "https://cloud.langfuse.com"

    # App config
    corpus_dir: str = "./corpus"
    chunk_size: int = 1200
    chunk_overlap: int = 200
    context_radius: int = 5
    max_search_results: int = 20

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def effective_llm_api_key(self) -> str:
        """Resolve LLM API key — provider-specific key or fallback."""
        if self.llm_api_key:
            return self.llm_api_key
        if self.llm_provider == "yandex":
            return self.yc_api_key
        return self.llm_api_key

    @property
    def effective_embed_api_key(self) -> str:
        """Resolve embedding API key — fallback to LLM key."""
        if self.embed_api_key:
            return self.embed_api_key
        if self.embed_provider == "yandex":
            return self.yc_api_key
        return self.effective_llm_api_key


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
