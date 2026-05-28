"""Runtime configuration for the HNF1B MCP server."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven settings (prefix HNF1B_MCP_)."""

    model_config = SettingsConfigDict(env_prefix="HNF1B_MCP_", env_file=".env")

    api_base_url: str = "https://api.hnf1b.org/api/v2"
    request_timeout_seconds: float = 30.0
    cache_ttl_default_seconds: int = 300
    host: str = "0.0.0.0"
    port: int = 8788
    protocol_version: str = "2025-11-25"
    default_response_mode: str = "compact"
    mode_char_budgets: dict[str, int] = {
        "minimal": 4000, "compact": 12000, "standard": 24000, "full": 48000,
    }
    max_response_chars_cap: int = 80000
    allowed_origins: list[str] = [
        "https://claude.ai", "https://claude.com",
    ]
    redis_url: str | None = None
    rate_limit_global_rps: float = 10.0


def get_settings() -> Settings:
    """Return a fresh Settings instance (call once at startup)."""
    return Settings()
