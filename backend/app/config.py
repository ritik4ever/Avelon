"""Application configuration loaded from environment variables."""

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Central configuration for the Avelon backend."""

    # App
    app_env: str = Field(default="development")
    app_name: str = Field(default="avelon")
    secret_key: str = Field(default="change-me")
    debug: bool = Field(default=False)

    # Database
    database_url: str = Field(default="postgresql+asyncpg://avelon_user:avelon_password@postgres:5432/avelon_db")
    database_url_sync: str = Field(default="postgresql://avelon_user:avelon_password@postgres:5432/avelon_db")

    # Redis
    redis_url: str = Field(default="redis://redis:6379/0")

    # JWT
    jwt_secret_key: str = Field(default="change-me-jwt-secret")
    jwt_access_token_expire_minutes: int = Field(default=30)
    jwt_refresh_token_expire_days: int = Field(default=7)
    jwt_algorithm: str = Field(default="HS256")

    # AI Providers
    openai_api_key: str = Field(default="")
    openai_model: str = Field(default="gpt-4o")
    anthropic_api_key: str = Field(default="")
    anthropic_model: str = Field(default="claude-3-5-sonnet-20241022")
    google_api_key: str = Field(default="")
    google_model: str = Field(default="gemini-1.5-pro")
    custom_openai_base_url: str = Field(default="")
    default_ai_provider: str = Field(default="openai")

    # Analyzer Runner
    analyzer_runner_url: str = Field(default="http://analyzer-runner:8001")

    # File Storage
    upload_dir: str = Field(default="/app/uploads")
    max_file_size_mb: int = Field(default=1)

    # Rate Limiting
    rate_limit_requests: int = Field(default=100)
    rate_limit_window_seconds: int = Field(default=60)

    # Logging
    log_level: str = Field(default="INFO")
    log_format: str = Field(default="json")

    # Red-team platform
    dataset_default_language: str = Field(default="solidity")
    adversarial_generation_timeout_seconds: int = Field(default=120)

    # CORS
    cors_allow_origins: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001,http://127.0.0.1:3001"
    )
    cors_allow_origin_regex: str = Field(default=r"https?://(localhost|127\.0\.0\.1)(:\d+)?")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "case_sensitive": False}

    @property
    def cors_origins(self) -> list[str]:
        """Return normalized CORS origins from comma-separated env value."""
        return [origin.strip() for origin in self.cors_allow_origins.split(",") if origin.strip()]


settings = Settings()
