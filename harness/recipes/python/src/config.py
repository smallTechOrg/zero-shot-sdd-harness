from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="APPNAME_",
        env_file=".env",
        extra="ignore",
    )

    # App
    env: str = "development"
    port: int = 8001

    # LLM
    llm_provider: str = "stub"   # stub | openai | anthropic | gemini
    llm_model: str = ""
    openai_api_key: SecretStr = SecretStr("")
    anthropic_api_key: SecretStr = SecretStr("")
    gemini_api_key: SecretStr = SecretStr("")

    # Database
    database_url: str = "postgresql+asyncpg://user:password@localhost:5432/appname"

    @property
    def resolved_llm_provider(self) -> str:
        return self.llm_provider.split("#")[0].strip()

    @property
    def is_stub(self) -> bool:
        return self.resolved_llm_provider == "stub"


@lru_cache
def get_settings() -> Settings:
    return Settings()
