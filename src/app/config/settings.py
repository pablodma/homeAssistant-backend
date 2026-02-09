"""Application settings loaded from environment variables."""

import json
from functools import lru_cache
from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # App
    app_name: str = "HomeAI API"
    app_env: str = "development"
    debug: bool = False

    # Database
    database_url: str = "postgresql://user:pass@localhost:5432/homeai"

    # Auth
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7  # 7 days

    # Google OAuth
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/v1/auth/google/callback"

    # Calendar OAuth URLs
    calendar_oauth_success_url: str = "http://localhost:3000/calendar/connected"
    calendar_oauth_error_url: str = "http://localhost:3000/calendar/error"

    # CORS - accepts JSON array or comma-separated string
    cors_origins: list[str] = ["http://localhost:3000"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> list[str]:
        """Parse CORS origins from JSON array or comma-separated string."""
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            # Try JSON first
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                pass
            # Fall back to comma-separated
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return ["http://localhost:3000"]

    # External Services
    openai_api_key: str = ""

    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
