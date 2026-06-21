from functools import lru_cache
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DAA_",
        env_file=".env",
        extra="ignore",
    )

    # App
    host: str = "127.0.0.1"
    port: int = 8001

    # LLM — default "stub" runs offline with no API key.
    # Switch to "gemini" and set DAA_GEMINI_API_KEY to go live.
    llm_provider: str = "stub"  # stub | gemini
    llm_model: str = "gemini-2.5-flash"
    gemini_api_key: SecretStr = SecretStr("")

    # Persistence
    duckdb_path: str = "./data/app.duckdb"
    sqlite_path: str = "./data/meta.db"

    # CORS
    cors_origins: list[str] = ["http://localhost:3000"]

    # Limits
    request_timeout_s: int = 30
    max_result_rows: int = 10000
    max_upload_bytes: int = 209715200  # 200 MB

    @property
    def resolved_llm_provider(self) -> str:
        return self.llm_provider.split("#")[0].strip()

    @property
    def is_stub(self) -> bool:
        return self.resolved_llm_provider == "stub"


@lru_cache
def get_settings() -> Settings:
    return Settings()
