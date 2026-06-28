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

    # Data-analysis agent (AGENT_ prefix) ----------------------------------
    # Gemini model used by every agent node. Env: AGENT_GEMINI_MODEL.
    gemini_model: str = Field(default="gemini-2.5-flash")
    # Bounded refinement-loop limit. Env: AGENT_MAX_STEPS.
    max_steps: int = Field(default=6)
    # Managed file store for uploaded datasets. Env: AGENT_DATASET_STORE_DIR.
    dataset_store_dir: str = Field(default="data/datasets")
    # Cost rates (USD per 1K tokens) for the daily/per-run cost meter.
    cost_per_1k_in: float = Field(default=0.0003)
    cost_per_1k_out: float = Field(default=0.0025)


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
