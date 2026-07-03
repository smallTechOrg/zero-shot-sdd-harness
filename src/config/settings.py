from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AGENT_",
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )

    database_url: str = Field(default="sqlite:///./data/agent.db")
    log_level: str = Field(default="INFO")

    # LLM provider — auto-detected from whichever key is set if left blank
    llm_provider: str = Field(default="")   # "anthropic" | "gemini"
    llm_model: str = Field(default="")      # uses provider default when blank

    # Provider keys — set exactly one
    anthropic_api_key: str = Field(default="")
    gemini_api_key: str = Field(default="")

    # Data-analysis agent tuning
    exec_timeout_seconds: int = Field(default=30)   # AGENT_EXEC_TIMEOUT_SECONDS
    max_code_retries: int = Field(default=3)        # AGENT_MAX_CODE_RETRIES

    def datasets_dir(self) -> Path:
        """Directory where uploaded dataset files are stored (data/datasets/).

        Derived from the current working directory (the repo root — all commands
        run from there). Created on demand by the upload endpoint.
        """
        return Path.cwd() / "data" / "datasets"


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
