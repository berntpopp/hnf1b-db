# app/config.py
import logging
import sys
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application settings configuration."""

    # PostgreSQL Database Configuration
    DATABASE_URL: str = ""  # Required, will be loaded from environment
    OLD_DATABASE_URL: str | None = None  # Optional, for migration purposes

    # Authentication
    JWT_SECRET: str = Field(default="")  # Required, will be loaded from environment

    # CORS Configuration
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173,http://localhost:8080"

    # Development Settings
    DEBUG: bool = False

    @field_validator("JWT_SECRET")
    @classmethod
    def validate_jwt_secret(cls, v: str) -> str:
        """Validate JWT_SECRET is set and non-empty.

        Fail fast on startup if JWT_SECRET is missing to prevent running
        with insecure configuration where tokens can be forged.
        """
        if not v or v.strip() == "":
            logger.critical(
                "JWT_SECRET is empty or not set! "
                "Set JWT_SECRET in .env file for secure authentication. "
                "Example: JWT_SECRET=$(openssl rand -hex 32)"
            )
            sys.exit(1)  # Fail fast - don't run with insecure config
        return v

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def validate_cors_origins(cls, v):
        """Ensure CORS_ORIGINS is a string."""
        if isinstance(v, list):
            return ",".join(v)
        return v

    def get_cors_origins_list(self) -> List[str]:
        """Convert CORS_ORIGINS string to list."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    class Config:
        """Pydantic configuration."""

        env_file = ".env"


settings = Settings()
