"""Application settings — loaded from environment / .env (DATA_ANALYST_ prefix).

Fails loud at startup if a required value (the Gemini API key) is missing — there is no
stub/offline mode (patterns/llm-providers.md). langchain-google-genai reads GOOGLE_API_KEY
from the process environment, so `configure_provider_env()` exports it from the loaded key.
"""

from __future__ import annotations

import os

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _strip_inline_comment(value: str) -> str:
    """pydantic-settings does not strip inline `#` comments — do it for enum-like values."""
    return value.split("#", 1)[0].strip()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DATA_ANALYST_",
        env_file=".env",
        extra="ignore",
    )

    gemini_api_key: str = Field(default="")
    llm_provider: str = Field(default="google_genai")
    llm_model: str = Field(default="gemini-2.5-flash")

    database_url: str = Field(default="sqlite+aiosqlite:///./datachat.db")

    max_iterations: int = Field(default=6)
    max_upload_bytes: int = Field(default=52_428_800)
    sample_rows: int = Field(default=20)

    log_level: str = Field(default="INFO")
    cors_origins: str = Field(default="http://localhost:3000")

    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in _strip_inline_comment(self.cors_origins).split(",") if o.strip()]

    @field_validator("llm_provider", "llm_model", "log_level", mode="before")
    @classmethod
    def _clean(cls, v: object) -> object:
        return _strip_inline_comment(v) if isinstance(v, str) else v

    def require_api_key(self) -> str:
        """Return the Gemini key or raise — call at startup so missing config fails loud."""
        key = _strip_inline_comment(self.gemini_api_key) if self.gemini_api_key else ""
        if not key:
            raise RuntimeError(
                "DATA_ANALYST_GEMINI_API_KEY is not set. DataChat is real-first — there is no "
                "stub mode. Set it in .env (see .env.example) or as an environment variable."
            )
        return key

    def configure_provider_env(self) -> None:
        """Export the key under the name langchain-google-genai expects (GOOGLE_API_KEY)."""
        os.environ["GOOGLE_API_KEY"] = self.require_api_key()


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
