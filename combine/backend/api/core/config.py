from __future__ import annotations

from pathlib import Path

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    project_name: str = "Prompcorp Tender Intelligence"
    postgres_user: str = "prompcorp"
    postgres_password: str = "change-me"
    postgres_db: str = "tender_intelligence"
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    redis_host: str = "redis"
    redis_port: int = 6379
    allowed_origins: str = "http://localhost:8080"
    ingestion_interval_seconds: int = 900
    enable_sample_data: bool = True
    session_secret_key: str = "change-this-session-secret"
    session_cookie_name: str = "prompcorp_session"
    session_max_age_seconds: int = 43200

    austender_source_url: str = ""
    nsw_etendering_source_url: str = ""
    vic_tenders_source_url: str = ""
    qld_procurement_source_url: str = ""
    prompcorp_pipeline_source_url: str = ""
    warroom_json_source_url: str = ""

    @computed_field
    @property
    def db_dsn(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @computed_field
    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/0"

    @computed_field
    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]

    @computed_field
    @property
    def sample_dir(self) -> Path:
        return Path(__file__).resolve().parents[2] / "ingestion" / "samples"


settings = Settings()
