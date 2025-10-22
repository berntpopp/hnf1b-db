"""Tests for application configuration and security settings."""

from unittest.mock import patch

import pytest

from app.config import Settings


class TestJWTSecretValidation:
    """Test JWT_SECRET security validation."""

    def test_jwt_secret_validation_fails_on_empty_string(self):
        """Test that empty JWT_SECRET causes startup failure."""
        with pytest.raises(SystemExit) as exc_info:
            Settings(JWT_SECRET="")
        assert exc_info.value.code == 1

    def test_jwt_secret_validation_fails_on_whitespace(self):
        """Test that whitespace-only JWT_SECRET causes startup failure."""
        with pytest.raises(SystemExit) as exc_info:
            Settings(JWT_SECRET="   ")
        assert exc_info.value.code == 1

    def test_jwt_secret_validation_succeeds_with_valid_secret(self):
        """Test that valid JWT_SECRET works."""
        settings = Settings(JWT_SECRET="test-secret-key-abc123")
        assert settings.JWT_SECRET == "test-secret-key-abc123"

    def test_jwt_secret_validation_succeeds_with_strong_secret(self):
        """Test that strong JWT_SECRET works."""
        strong_secret = "a" * 32  # 32 character secret
        settings = Settings(JWT_SECRET=strong_secret)
        assert settings.JWT_SECRET == strong_secret

    @patch("app.config.logger")
    def test_jwt_secret_validation_logs_critical_error(self, mock_logger):
        """Test that empty JWT_SECRET logs critical error."""
        with pytest.raises(SystemExit):
            Settings(JWT_SECRET="")

        # Verify critical log was called
        mock_logger.critical.assert_called_once()
        call_args = mock_logger.critical.call_args[0][0]
        assert "JWT_SECRET is empty" in call_args
        assert "Set JWT_SECRET in .env file" in call_args


class TestCORSConfiguration:
    """Test CORS configuration validation."""

    def test_cors_origins_string_conversion(self):
        """Test CORS_ORIGINS converts list to string."""
        settings = Settings(
            JWT_SECRET="test-secret",
            CORS_ORIGINS=["http://localhost:3000", "http://localhost:8080"]
        )
        assert isinstance(settings.CORS_ORIGINS, str)
        assert "http://localhost:3000" in settings.CORS_ORIGINS

    def test_cors_origins_list_parsing(self):
        """Test get_cors_origins_list() parses string correctly."""
        settings = Settings(
            JWT_SECRET="test-secret",
            CORS_ORIGINS="http://localhost:3000,http://localhost:8080"
        )
        origins = settings.get_cors_origins_list()
        assert len(origins) == 2
        assert "http://localhost:3000" in origins
        assert "http://localhost:8080" in origins


class TestDatabaseConfiguration:
    """Test database configuration."""

    def test_database_url_can_be_set(self):
        """Test DATABASE_URL can be configured."""
        db_url = "postgresql+asyncpg://user:pass@localhost:5432/testdb"
        settings = Settings(JWT_SECRET="test-secret", DATABASE_URL=db_url)
        assert settings.DATABASE_URL == db_url

    def test_old_database_url_optional(self):
        """Test OLD_DATABASE_URL is optional."""
        # Create settings without specifying OLD_DATABASE_URL
        # Note: May be loaded from .env if present, so just check it's nullable
        settings = Settings(JWT_SECRET="test-secret", OLD_DATABASE_URL=None)
        assert settings.OLD_DATABASE_URL is None
