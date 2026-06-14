from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DATACHAT_",
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )

    database_url: str = Field(default="sqlite:///./datachat.db")
    llm_model: str = Field(default="gemini-2.5-flash")
    upload_dir: str = Field(default="uploads")
    log_level: str = Field(default="INFO")


class GeminiSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )

    gemini_api_key: str = Field(default="")


_settings: Settings | None = None
_gemini_settings: GeminiSettings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def get_gemini_settings() -> GeminiSettings:
    global _gemini_settings
    if _gemini_settings is None:
        _gemini_settings = GeminiSettings()
    return _gemini_settings
