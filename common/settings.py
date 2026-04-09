from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class CommonSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openrouter_api_key: str | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_text_model: str = "google/gemini-2.5-flash"
    openrouter_reasoning_model: str = "anthropic/claude-3.5-sonnet"
    openrouter_image_model: str = "google/gemini-2.5-flash-image"
    default_temperature: float = 0.2

    apify_api_token: str | None = None
    elevenlabs_api_key: str | None = None
    heygen_api_key: str | None = None
    quickreel_api_key: str | None = None
    facebook_access_token: str | None = None
    instagram_business_account_id: str | None = None

    twitter_consumer_key: str | None = None
    twitter_consumer_secret: str | None = None
    twitter_access_token: str | None = None
    twitter_access_token_secret: str | None = None

    linkedin_access_token: str | None = None
    linkedin_author_urn: str | None = None

    google_service_account_json: str | None = None
    google_sheet_id: str | None = None

    request_timeout_seconds: int = 90
    poll_interval_seconds: int = 15
    max_poll_attempts: int = 24
    artifact_root: Path = Field(
        default_factory=lambda: Path.cwd() / "artifacts",
    )


class MissingConfigurationError(RuntimeError):
    """Raised when a workflow needs a credential that is not configured."""
