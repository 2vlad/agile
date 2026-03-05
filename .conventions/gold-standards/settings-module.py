"""Gold standard: Settings module pattern.

Use pydantic-settings BaseSettings with lru_cache singleton.
All config comes from environment / .env — never hardcode values.
"""
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    api_key: str
    database_url: str
    some_list: list[int] = Field(default_factory=list)

    @field_validator("some_list", mode="before")
    @classmethod
    def parse_csv(cls, v: object) -> list[int]:
        if isinstance(v, str):
            return [int(x.strip()) for x in v.split(",") if x.strip()]
        return v  # type: ignore[return-value]

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def computed_uri(self) -> str:
        return self.explicit_uri or f"default://{self.api_key}/latest"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
