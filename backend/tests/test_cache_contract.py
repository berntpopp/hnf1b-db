"""Tests for the Redis fallback contract."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.core.cache import CacheService
from app.core.config import EmailConfig, Settings, YamlConfig


def build_yaml_config(*, email_backend: str = "console") -> YamlConfig:
    """Build a minimal YAML config for settings tests."""
    return YamlConfig(email=EmailConfig(backend=email_backend))


@pytest.mark.asyncio
async def test_development_redis_failure_uses_in_memory_fallback():
    """Development permits Redis fallback when Redis is unavailable."""
    cache = CacheService()
    with patch(
        "app.core.config.load_yaml_config",
        lambda: build_yaml_config(email_backend="console"),
    ):
        settings = Settings(
            JWT_SECRET="test-secret",
            ADMIN_PASSWORD="test-admin-password",
            environment="development",
            AUTH_COOKIE_SECURE=False,
            enable_dev_auth=False,
            _env_file=None,
        )
    redis_client = Mock()
    redis_client.ping = AsyncMock(side_effect=OSError("redis down"))
    redis_client.aclose = AsyncMock()

    with (
        patch("app.core.config.settings", settings),
        patch("app.core.cache.aioredis.from_url", return_value=redis_client),
    ):
        await cache.connect("redis://example.test:6379/0")

    assert cache.is_connected is False
    await cache.set("key", "value", ttl=60)
    assert await cache.get("key") == "value"
    redis_client.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_production_redis_failure_raises_and_disables_fallback():
    """Production refuses startup when Redis is unavailable."""
    cache = CacheService()
    with patch(
        "app.core.config.load_yaml_config",
        lambda: build_yaml_config(email_backend="smtp"),
    ):
        settings = Settings(
            JWT_SECRET="test-secret",
            ADMIN_PASSWORD="test-admin-password",
            environment="production",
            AUTH_COOKIE_SECURE=True,
            SMTP_HOST="smtp.example.test",
            SMTP_USERNAME="smtp-user",
            SMTP_PASSWORD="smtp-password",
            enable_dev_auth=False,
            _env_file=None,
        )
    redis_client = Mock()
    redis_client.ping = AsyncMock(side_effect=OSError("redis down"))
    redis_client.aclose = AsyncMock()

    with (
        patch("app.core.config.settings", settings),
        patch("app.core.cache.aioredis.from_url", return_value=redis_client),
    ):
        with pytest.raises(RuntimeError, match="Redis is required"):
            await cache.connect("redis://example.test:6379/0")

    assert cache.is_connected is False
    redis_client.aclose.assert_awaited_once()
