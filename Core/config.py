"""Application settings — replaces server/config/env.js."""

from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Backend root (Core/config.py -> Backend/)
BASE_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    PORT: int = 5000
    NODE_ENV: str = "development"
    DATABASE_URL: str = Field(
        ...,
        description="PostgreSQL URL, e.g. postgresql+asyncpg://user:pass@localhost:5432/society_management",
    )
    CLIENT_ORIGIN: str
    JWT_SECRET: str
    JWT_REFRESH_SECRET: str

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    BCRYPT_ROUNDS: int = 12

    @property
    def is_production(self) -> bool:
        return self.NODE_ENV.lower() == "production"

    @property
    def allowed_origins(self) -> List[str]:
        return [o.strip() for o in self.CLIENT_ORIGIN.split(",") if o.strip()]

    @field_validator("JWT_SECRET", "JWT_REFRESH_SECRET")
    @classmethod
    def secrets_must_not_be_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("JWT secrets must be non-empty")
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
