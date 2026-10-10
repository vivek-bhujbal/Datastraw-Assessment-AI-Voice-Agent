from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    gemini_api_key: str = ""
    llm_model: str = "gemini-3.5-flash-lite"
    stt_model: str = "gemini-3.5-flash-lite"
    tts_model: str = "gemini-3.8-flash-lite-tts"
    tts_voice: str = "Kore"
    frontend_origins: str = "http://localhost:3000"
    max_sessions: int = Field(default=8, ge=1, le=100)

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[1] / ".env",
        env_file_encoding="utf-8-sig",
        extra="ignore"
    )

    @property
    def origins(self):
        return [value.strip().rstrip("/") for value in self.frontend_origins.split(",")]

    @property
    def ready(self):
        key = self.gemini_api_key.strip()
        return bool(key and not key.startswith(("your-", "sk-")))


def get_settings():
    return Settings()

