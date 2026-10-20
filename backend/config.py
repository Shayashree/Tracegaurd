"""Configuration settings and environment management for TraceGuard."""
import logging
from pathlib import Path
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger("traceguard.config")

# Determine base repository directory
BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    BASE_DIR: Path = BASE_DIR

    # Environment & Logging
    TRACEGUARD_ENV: str = "development"  # "development", "testing", "production"
    LOG_LEVEL: str = "INFO"
    APP_VERSION: str = "0.7.0"

    # API Networking
    API_HOST: str = "127.0.0.1"
    API_PORT: int = 8000
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:80",
        "http://127.0.0.1:80",
    ]

    # Agent Limits
    DEFAULT_MAX_STEPS: int = 8
    DEFAULT_TIMEOUT_SECONDS: float = 30.0

    # Storage and Data Paths
    DATABASE_PATH: str = str(BASE_DIR / "traceguard.db")
    DATA_DIR: str = str(BASE_DIR / "data")

    # Recovery Safety Budgets (Milestone 4 & 7)
    RECOVERY_BUDGET_MAX_ATTEMPTS: int = 2
    RECOVERY_BUDGET_MAX_STEPS: int = 5
    RECOVERY_BUDGET_MAX_TOOLS: int = 5

    # Pluggable Model Selection
    MODEL_ADAPTER: str = "mock"  # "mock" or "openai"
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL_NAME: str = "gpt-4o-mini"
    OPENAI_BASE_URL: Optional[str] = None

    @property
    def is_production(self) -> bool:
        return self.TRACEGUARD_ENV.lower() == "production"

    @property
    def is_testing(self) -> bool:
        return self.TRACEGUARD_ENV.lower() == "testing"

    @property
    def products_json_path(self) -> Path:
        return Path(self.DATA_DIR) / "products.json"

    @property
    def documents_dir_path(self) -> Path:
        return Path(self.DATA_DIR) / "documents"

    def validate_configuration(self) -> List[str]:
        """Validate startup configuration and return non-fatal advisory warnings."""
        warnings: List[str] = []

        # Validate database parent path exists or is creatable
        db_path = Path(self.DATABASE_PATH)
        if not db_path.parent.exists():
            try:
                db_path.parent.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                warnings.append(f"Cannot create database directory {db_path.parent}: {e}")

        # Validate model provider credentials if live adapter selected
        if self.MODEL_ADAPTER == "openai":
            if not self.OPENAI_API_KEY:
                if self.is_production:
                    raise ValueError(
                        "MODEL_ADAPTER is set to 'openai' in production, but OPENAI_API_KEY is not configured."
                    )
                warnings.append("MODEL_ADAPTER='openai' but OPENAI_API_KEY is missing; adapter will reject live queries.")

        # In production, disallow wildcard or overly permissive settings if set
        if self.is_production:
            if "*" in self.CORS_ORIGINS:
                warnings.append("Production environment has wildcard CORS '*' enabled. Configure explicit trusted origins.")

        return warnings

settings = Settings()
