from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator


class Settings(BaseSettings):
    # Telegram
    telegram_token: str
    admin_user_ids: list[int] = Field(default_factory=list)

    @field_validator("admin_user_ids", mode="before")
    @classmethod
    def parse_admin_ids(cls, v: object) -> list[int]:
        if isinstance(v, str):
            return [int(x.strip()) for x in v.split(",") if x.strip()]
        if isinstance(v, int):
            return [v]
        return v  # type: ignore[return-value]

    # Yandex Cloud
    yc_api_key: str
    yc_folder_id: str
    yc_llm_model: str = Field(default="")
    yc_embed_doc_model: str = Field(default="")
    yc_embed_query_model: str = Field(default="")
    yc_llm_base_url: str = "https://ai.api.cloud.yandex.net/v1"
    yc_embeddings_url: str = "https://llm.api.cloud.yandex.net/foundationModels/v1/textEmbedding"

    # Database
    database_url: str
    db_statement_cache_size: int = 0  # 0 for PgBouncer compatibility

    # App config
    corpus_dir: str = "./corpus"
    chunk_size: int = 1200
    chunk_overlap: int = 200
    max_agent_iterations: int = 4
    context_radius: int = 5
    max_search_results: int = 20

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def llm_model(self) -> str:
        return self.yc_llm_model or f"gpt://{self.yc_folder_id}/yandexgpt/latest"

    @property
    def embed_doc_model(self) -> str:
        return self.yc_embed_doc_model or f"emb://{self.yc_folder_id}/text-search-doc/latest"

    @property
    def embed_query_model(self) -> str:
        return self.yc_embed_query_model or f"emb://{self.yc_folder_id}/text-search-query/latest"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
