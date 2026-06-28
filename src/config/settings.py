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
    llm_model: str = Field(default="gemini-2.5-flash")  # Flash tier for low cost

    # Provider keys — set exactly one
    anthropic_api_key: str = Field(default="")
    gemini_api_key: str = Field(default="")

    # --- Privacy boundary ---
    # Max sample rows sent to the LLM (schema + these rows only; full data stays local).
    sample_rows: int = Field(default=10)

    # --- Cost guard (hard step cap) ---
    max_steps: int = Field(default=5)
    # Max rows returned from any local analysis step (bounded aggregates only).
    max_result_rows: int = Field(default=1000)

    # --- Cost accounting (Gemini Flash pricing, USD per 1M tokens) ---
    price_in_per_m: float = Field(default=0.30)
    price_out_per_m: float = Field(default=2.50)

    # --- Upload limits ---
    max_upload_mb: int = Field(default=100)


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
