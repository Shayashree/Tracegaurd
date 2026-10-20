"""Configuration settings for TraceGuard."""
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

# Determine base repository directory
BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    TRACEGUARD_ENV: str = "development"
    LOG_LEVEL: str = "INFO"

    # Agent Limits
    DEFAULT_MAX_STEPS: int = 8
    DEFAULT_TIMEOUT_SECONDS: float = 30.0

    # Storage and Data Paths
    DATABASE_PATH: str = str(BASE_DIR / "traceguard.db")
    DATA_DIR: str = str(BASE_DIR / "data")

    # Pluggable Model Selection
    MODEL_ADAPTER: str = "mock"  # "mock" or "openai"
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL_NAME: str = "gpt-4o-mini"
    OPENAI_BASE_URL: Optional[str] = None

    @property
    def products_json_path(self) -> Path:
        return Path(self.DATA_DIR) / "products.json"

    @property
    def documents_dir_path(self) -> Path:
        return Path(self.DATA_DIR) / "documents"

settings = Settings()
