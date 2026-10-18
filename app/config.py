"""Application configuration loaded from environment variables.

All secrets and environment-specific values live here. Never hard-code secrets
in source. See ``.env.example`` for the full list of supported variables.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central settings object.

    Values are read from environment variables (case-insensitive) and an
    optional ``.env`` file during local development.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- General ---
    app_name: str = "TraceGuard AI"
    environment: Literal["development", "test", "production"] = "development"
    debug: bool = True
    api_v1_prefix: str = "/api/v1"
    log_level: str = "INFO"

    # --- CORS ---
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    # --- Auth ---
    jwt_secret: str = Field(default="change-me-in-production", min_length=8)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_minutes: int = 60 * 24 * 7

    # --- PostgreSQL ---
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_user: str = "traceguard"
    postgres_password: str = "traceguard"
    postgres_db: str = "traceguard"

    # --- Neo4j ---
    neo4j_uri: str = "bolt://neo4j:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "traceguard123"

    # --- Object storage (MinIO / S3) ---
    s3_endpoint_url: str = "http://minio:9000"
    s3_region: str = "us-east-1"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket_evidence: str = "evidence"
    s3_bucket_reports: str = "reports"
    s3_use_ssl: bool = False
    # Optional: enable only when the configured S3-compatible store supports it.
    # Local MinIO has no KMS configured by default, so leave this unset locally.
    s3_server_side_encryption: str | None = None

    # --- LLM provider ---
    # mode=mock keeps the whole platform functional offline (hackathon-safe default).
    llm_mode: Literal["openai", "mock"] = "mock"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.0
    llm_timeout_seconds: int = 30
    llm_max_retries: int = 2

    # --- External intelligence APIs (mock-first) ---
    osint_mode: Literal["live", "mock"] = "mock"
    crypto_mode: Literal["live", "mock"] = "mock"
    virustotal_api_key: str = ""
    etherscan_api_key: str = ""
    etherscan_base_url: str = "https://api.etherscan.io/api"
    external_allowlist: str = "api.etherscan.io,www.virustotal.com,rdap.org"
    external_timeout_seconds: int = 10
    external_max_retries: int = 2

    # --- IBM Z integration ---
    # real => call ML for z/OS endpoint; mock => clearly-labelled simulated scoring.
    ibmz_mode: Literal["real", "mock"] = "mock"
    ibmz_endpoint: str = ""
    ibmz_api_token: str = ""
    ibmz_timeout_seconds: int = 10

    # --- Evidence processing limits ---
    max_upload_bytes: int = 25 * 1024 * 1024  # 25 MiB
    allowed_mime_types: str = (
        "image/jpeg,image/png,image/gif,image/tiff,"
        "application/pdf,text/plain,text/csv,text/xml,text/markdown,"
        "application/json,application/xml,"
        "application/zip,"
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document,"
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,"
        "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    )
    exiftool_timeout_seconds: int = 30
    zip_max_entries: int = 1000
    zip_max_ratio: int = 100
    # Cap on characters extracted per file for content/IOC scanning (bounded work).
    content_extract_max_chars: int = 500_000
    # Cap on indicators auto-registered from file content per investigation run.
    content_max_indicators_per_run: int = 500

    # --- Orchestration ---
    agent_timeout_seconds: int = 60
    agent_max_retries: int = 2
    defense_max_rounds: int = 2

    @property
    def database_url(self) -> str:
        """Async SQLAlchemy connection string."""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def sync_database_url(self) -> str:
        """Sync connection string (used by Alembic migrations)."""
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def allowed_mime_list(self) -> list[str]:
        return [m.strip() for m in self.allowed_mime_types.split(",") if m.strip()]

    @property
    def external_allowlist_set(self) -> set[str]:
        return {h.strip().lower() for h in self.external_allowlist.split(",") if h.strip()}


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
