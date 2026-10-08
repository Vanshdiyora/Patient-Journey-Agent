from functools import lru_cache
import json
import secrets
from pathlib import Path
from typing import Annotated
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]

class Settings(BaseSettings):
    app_name: str = "Patient Journey Orchestrator API"
    app_env: str = "development"
    debug: bool = False
    api_prefix: str = "/api/v1"
    database_url: str

    auth_jwt_secret: str = Field(default_factory=lambda: secrets.token_urlsafe(48))
    auth_jwt_expires_minutes: int = 480

    cors_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:3000",
        "http://localhost:5173",
    ]

    maq_ai_base_url: str = "https://llm.maqsoftware.net/v1"
    maq_ai_api_key: str = ""
    maq_ai_model: str = "qwen-3.8-27b"
    maq_ai_timeout_seconds: int = 600
    maq_ai_temperature: float = 0.0
    maq_ai_enabled: bool = True

    # Outbound patient notifications (reminders, document/appointment requests).
    # When smtp_host and smtp_from are empty the app uses the mock services.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_use_tls: bool = True
    # Safety net for testing: when set, every email goes to this address instead.
    smtp_redirect_to: str = ""

    supervisor_max_iterations: int = 6
    agent_context_event_limit: int = 12

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def email_enabled(self) -> bool:
        return bool(self.smtp_host and self.smtp_from)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value):
        if isinstance(value, str):
            value = value.strip()
            if value.startswith("["):
                value = json.loads(value)
            else:
                value = value.split(",")
        if not isinstance(value, list) or not all(
            isinstance(origin, str) and origin.strip() for origin in value
        ):
            raise ValueError("CORS_ORIGINS must be a comma-separated string or a JSON array of URLs")
        return [origin.strip() for origin in value]

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value):
        # Use the driver in requirements.txt regardless of SQLAlchemy defaults.
        # Keep credentials and Neon SSL/query options exactly as provided.
        if isinstance(value, str):
            for prefix in ("postgres://", "postgresql://"):
                if value.startswith(prefix):
                    return "postgresql+psycopg2://" + value[len(prefix):]
        return value

@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
