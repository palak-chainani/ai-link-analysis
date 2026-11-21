"""Application settings loaded from environment variables (T02)."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Provider = Literal["gemini", "openai", "anthropic"]


class Settings(BaseSettings):
    """All runtime configuration. Secrets come from the environment only."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Provider selection
    llm_provider: Provider = "gemini"
    fallback_provider: Provider = "openai"

    # Provider credentials (never logged, never returned)
    gemini_api_key: str | None = None
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None

    # Model identifiers
    gemini_model: str = "gemini-3.5-flash-lite"
    fallback_model: str = "gpt-5-mini"  # model id used for the OpenAI provider
    anthropic_model: str = "claude-haiku-4-5"

    # Fetching limits
    request_timeout_seconds: float = Field(default=10.0, gt=0)
    llm_timeout_seconds: float = Field(default=45.0, gt=0)
    max_fetch_bytes: int = Field(default=5_000_000, gt=0)
    max_content_tokens: int = Field(default=15_000, gt=0)
    max_url_length: int = Field(default=2048, gt=0)
    max_redirects: int = Field(default=5, ge=0)

    # Generation controls
    temperature: float = Field(default=0.2, ge=0, le=1)
    max_output_tokens: int = Field(default=4000, gt=0)
    max_retries: int = Field(default=1, ge=0, le=3)

    # Cache and diagnostics
    cache_ttl_seconds: int = Field(default=3600, gt=0)
    log_level: str = "INFO"

    @field_validator("gemini_model", "fallback_model", "anthropic_model")
    @classmethod
    def model_id_required(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("Model identifier must not be empty")
        return value.strip()

    @field_validator("log_level")
    @classmethod
    def valid_log_level(cls, value: str) -> str:
        normalised = value.strip().upper()
        if normalised not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("log_level must be a standard Python log level")
        return normalised

    def api_key_for(self, provider: str) -> str | None:
        """Return the key for a provider, or None when it is not configured."""
        return {
            "gemini": self.gemini_api_key,
            "openai": self.openai_api_key,
            "anthropic": self.anthropic_api_key,
        }.get(provider)

    def model_for(self, provider: str) -> str:
        """Return the configured model id for a provider."""
        return {
            "gemini": self.gemini_model,
            "openai": self.fallback_model,
            "anthropic": self.anthropic_model,
        }[provider]

    def configured_providers(self) -> list[str]:
        """Providers with a usable key, in preferred order."""
        order = [
            self.llm_provider,
            self.fallback_provider,
            "gemini",
            "openai",
            "anthropic",
        ]
        result: list[str] = []
        for provider in order:
            if provider not in result and self.api_key_for(provider):
                result.append(provider)
        return result


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a single validated settings instance for the process."""
    return Settings()
