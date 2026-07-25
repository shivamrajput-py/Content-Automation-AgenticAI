from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ModuleNotFoundError:
    def SettingsConfigDict(**kwargs):
        return kwargs

    class BaseSettings(BaseModel):
        model_config = {"extra": "ignore"}

        def __init__(self, **data):
            merged = {**self._load_env_values(), **data}
            super().__init__(**merged)

        @classmethod
        def _load_env_values(cls) -> dict[str, str]:
            config = getattr(cls, "model_config", {}) or {}
            env_values: dict[str, str] = {}

            env_file = config.get("env_file")
            if env_file:
                env_path = Path(env_file)
                if env_path.exists():
                    for line in env_path.read_text(encoding="utf-8").splitlines():
                        stripped = line.strip()
                        if not stripped or stripped.startswith("#") or "=" not in stripped:
                            continue
                        key, value = stripped.split("=", 1)
                        env_values[key.strip()] = value.strip()

            env_values.update(os.environ)
            loaded: dict[str, str] = {}
            for field_name in cls.model_fields:
                env_name = field_name.upper()
                if env_name in env_values:
                    loaded[field_name] = env_values[env_name]
            return loaded


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
    artifact_root: Path = Field(default_factory=lambda: Path.cwd() / "artifacts")


class MissingConfigurationError(RuntimeError):
    """Raised when a workflow needs a credential that is not configured."""
