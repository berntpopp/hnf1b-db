# app/config.py
import os
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings configuration."""

    # PostgreSQL Database Configuration
    DATABASE_URL: str = ""  # Required, will be loaded from environment
    OLD_DATABASE_URL: str | None = None  # Optional, for migration purposes

    # Authentication
    JWT_SECRET: str = ""  # Required, will be loaded from environment

    # CORS Configuration
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8080"

    # Development Settings
    DEBUG: bool = False

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
