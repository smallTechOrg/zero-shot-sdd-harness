import os
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DA_",
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )

    gemini_api_key: str = Field(default="")
    llm_model: str = Field(default="gemini-2.5-flash")
    database_url: str = Field(default="sqlite:///data/data_analyst.db")
    duckdb_path: str = Field(default="data/duckdb.db")
    upload_dir: str = Field(default="data/uploads")
    max_history_turns: int = Field(default=20)
    summary_keep_turns: int = Field(default=6)
    max_tool_rounds: int = Field(default=10)
    port: int = Field(default=8001)
    log_level: str = Field(default="INFO")

    @model_validator(mode="after")
    def _fallback_gemini_key(self) -> "Settings":
        # .env uses GEMINI_API_KEY (no prefix); DA_GEMINI_API_KEY is the prefixed form.
        # pydantic-settings reads DA_GEMINI_API_KEY automatically; fall back to the
        # unprefixed GEMINI_API_KEY so both forms work without requiring users to rename.
        if not self.gemini_api_key:
            self.gemini_api_key = os.environ.get("GEMINI_API_KEY", "")
        return self


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
