# app/config.py
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings configuration."""

    # PostgreSQL Database Configuration
    DATABASE_URL: str
    OLD_DATABASE_URL: str | None = None  # Optional, for migration purposes

    # Authentication
    JWT_SECRET: str

    # Development Settings
    DEBUG: bool = False

    class Config:
        """Pydantic configuration."""

        env_file = ".env"


settings = Settings()
