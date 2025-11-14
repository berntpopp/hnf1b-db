# app/config.py
import logging
import sys
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application settings configuration."""

    # PostgreSQL Database Configuration
    DATABASE_URL: str = ""  # Required, will be loaded from environment
    OLD_DATABASE_URL: str | None = None  # Optional, for migration purposes

    # Authentication - JWT
    JWT_SECRET: str = Field(default="")  # Required, will be loaded from environment
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Authentication - Password Security
    PASSWORD_MIN_LENGTH: int = 8
    MAX_LOGIN_ATTEMPTS: int = 5
    ACCOUNT_LOCKOUT_MINUTES: int = 15

    # Default Admin Credentials (for initial setup)
    ADMIN_USERNAME: str = "admin"
    ADMIN_EMAIL: str = "admin@hnf1b-db.local"
    ADMIN_PASSWORD: str = "ChangeMe!Admin2025"

    # CORS Configuration
    CORS_ORIGINS: str = (
        "http://localhost:3000,http://localhost:5173,http://localhost:8080"
    )

    # Development Settings
    DEBUG: bool = False

    # Ensembl VEP API Configuration
    VEP_API_BASE_URL: str = "https://rest.ensembl.org"
    VEP_RATE_LIMIT_REQUESTS_PER_SECOND: int = 15
    VEP_REQUEST_TIMEOUT_SECONDS: int = 30
    VEP_MAX_RETRIES: int = 3
    VEP_RETRY_BACKOFF_FACTOR: float = 2.0  # Exponential backoff: 1s, 2s, 4s, etc.
    VEP_CACHE_ENABLED: bool = True
    VEP_CACHE_SIZE_LIMIT: int = 1000  # Max cached variants

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

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
