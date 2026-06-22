from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ANALYST_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    gemini_api_key: str = Field(default="")
    data_dir: Path = Field(default=Path("./data"))
    token_budget_hard_cap: int = Field(default=32000)
    prompt_caching_enabled: bool = Field(default=True)
    backend_port: int = Field(default=8001)
    frontend_port: int = Field(default=3000)
    gemini_llm_model: str = Field(default="gemini-2.5-flash")
    database_url: str = Field(default="sqlite:///./data/session.db")

    @property
    def absolute_database_url(self) -> str:
        """Return an absolute SQLite URL resolved from current working dir."""
        if self.database_url.startswith("sqlite:///./"):
            rel = self.database_url[len("sqlite:///./"):]
            return f"sqlite:///{Path(rel).resolve()}"
        return self.database_url

    @property
    def resolved_data_dir(self) -> Path:
        return Path(self.data_dir).resolve()


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
