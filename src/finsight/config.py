from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "local"
    app_name: str = "FinSight AI"
    log_level: str = "INFO"
    api_host: str = "127.0.0.1"
    api_port: int = Field(default=8000, gt=0, le=65535)
    llm_provider: str = "mock"
    aws_region: str = "us-east-1"
    bedrock_model_id: str = ""
    aws_profile: str | None = None
    llm_timeout_seconds: float = Field(default=20, gt=0, le=120)
    llm_max_output_tokens: int = Field(default=400, gt=0, le=2048)
    cache_ttl_seconds: int = Field(default=300, gt=0)
    request_timeout_seconds: float = Field(default=20, gt=0, le=120)
    max_concurrent_agents: int = Field(default=4, gt=0, le=32)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
