from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# The single source-of-truth .env lives at the repo root, regardless of the
# working directory the backend is launched from (e.g. `cd backend && uvicorn`).
_ROOT_ENV = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(_ROOT_ENV), extra="ignore")

    app_env: str = "dev"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_auth_token: str = Field(default="dev-token", min_length=8)
    app_default_user_id: int = 1
    max_upload_mb: int = 50
    cors_origins: str = "http://localhost:3000"
    # Preload the embedder + reranker at API startup (in a background thread) so
    # the first chat doesn't pay the model load/download cost mid-request.
    warm_models_on_startup: bool = True

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "research_o_writer"
    postgres_user: str = "row"
    postgres_password: str = "row_dev_password"

    redis_host: str = "localhost"
    redis_port: int = 6379

    s3_endpoint: str = "http://localhost:9000"
    s3_access_key: str = "row_minio_access"
    s3_secret_key: str = "row_minio_secret"
    s3_bucket: str = "research-o-writer"
    s3_region: str = "us-east-1"

    anthropic_api_key: str = ""
    anthropic_model_default: str = "claude-sonnet-4-6"
    anthropic_model_hard: str = "claude-opus-4-7"

    embedding_model: str = "BAAI/bge-m3"
    embedding_dim: int = 1024
    reranker_model: str = "BAAI/bge-reranker-v2-m3"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def database_url_sync(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/0"


@lru_cache
def get_settings() -> Settings:
    return Settings()
