"""Application settings loaded from environment variables."""

import json
from functools import lru_cache

from pydantic import Field
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

    # CORS - stored as string to avoid pydantic-settings JSON parsing issues
    cors_origins_str: str = Field(default="http://localhost:3000", validation_alias="cors_origins")

    # External Services
    openai_api_key: str = ""

    # GitHub API (for prompt editing)
    github_token: str = ""  # Personal Access Token with repo write access
    github_repo: str = "pablodma/homeAssistant-asistant"  # owner/repo
    github_branch: str = "master"

    # Frontend URL (para redirects de Mercado Pago)
    frontend_url: str = "http://localhost:3000"

    # Mercado Pago
    mp_access_token: str = ""  # Token privado de MP
    mp_public_key: str = ""  # Clave publica para frontend
    mp_webhook_secret: str = ""  # Para validar firma de webhooks (opcional)
    mp_sandbox: bool = True  # True para ambiente de pruebas

    # Anthropic (Claude) - QA Reviewer
    anthropic_api_key: str = ""  # API key for Claude
    qa_review_model: str = "claude-sonnet-4-20250514"  # Claude model for QA reviews
    qa_review_max_improvements: int = 3  # Max prompts to modify per review cycle
    qa_review_cooldown_hours: int = 24  # Hours before same agent prompt can be modified again
    qa_review_min_issues: int = 2  # Minimum issues to trigger improvement for an agent

    @property
    def cors_origins(self) -> list[str]:
        """Parse CORS origins from string (JSON array, comma-separated, or bracketed)."""
        raw = self.cors_origins_str.strip()
        
        # Remove surrounding brackets if present (Railway UI adds them)
        if raw.startswith("[") and raw.endswith("]"):
            raw = raw[1:-1]
        
        # Try JSON array first (properly quoted)
        try:
            parsed = json.loads(f"[{raw}]") if not raw.startswith('"') else json.loads(raw)
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            pass
        
        # Fall back to comma-separated
        return [origin.strip() for origin in raw.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
