from __future__ import annotations

from functools import lru_cache
from typing import List, Literal, Optional

from pydantic import AnyHttpUrl, BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class TokenConfig(BaseModel):
    token: str
    label: str
    rpm: int = Field(gt=0)
    rpd: int = Field(gt=0)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)

    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8080, alias="PORT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    default_backend: Literal["ollama", "vllm"] = Field(alias="DEFAULT_BACKEND")
    ollama_base_url: Optional[AnyHttpUrl] = Field(default=None, alias="OLLAMA_BASE_URL")
    vllm_base_url: Optional[AnyHttpUrl] = Field(default=None, alias="VLLM_BASE_URL")

    tokens_json: List[TokenConfig] = Field(default_factory=list, alias="TOKENS_JSON")

    rate_limit_store: Literal["memory", "redis"] = Field(default="memory", alias="RATE_LIMIT_STORE")
    redis_url: Optional[str] = Field(default=None, alias="REDIS_URL")

    max_body_bytes: int = Field(default=2 * 1024 * 1024, alias="MAX_BODY_BYTES")

    cache_models_ttl: int = Field(default=300, alias="MODEL_CACHE_TTL")

    @property
    def ollama_enabled(self) -> bool:
        return self.ollama_base_url is not None

    @property
    def vllm_enabled(self) -> bool:
        return self.vllm_base_url is not None

    def validate_backends(self) -> None:
        if self.default_backend == "ollama" and not self.ollama_enabled:
            raise ValueError("DEFAULT_BACKEND set to ollama but OLLAMA_BASE_URL missing")
        if self.default_backend == "vllm" and not self.vllm_enabled:
            raise ValueError("DEFAULT_BACKEND set to vllm but VLLM_BASE_URL missing")
        if not self.tokens_json:
            raise ValueError("TOKENS_JSON must provide at least one token")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.validate_backends()
    return settings
