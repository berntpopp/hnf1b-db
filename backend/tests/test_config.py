"""Tests for application configuration and security settings."""

from unittest.mock import patch

import pytest

from app.core.config import Settings


class TestJWTSecretValidation:
    """Test JWT_SECRET security validation."""

    def test_config_jwt_secret_empty_raises_error(self):
        """Test that empty JWT_SECRET raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            Settings(JWT_SECRET="")
        assert "JWT_SECRET is required" in str(exc_info.value)

    def test_config_jwt_secret_whitespace_raises_error(self):
        """Test that whitespace-only JWT_SECRET raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            Settings(JWT_SECRET="   ")
        assert "JWT_SECRET is required" in str(exc_info.value)

    def test_config_jwt_secret_valid_succeeds(self):
        """Test that valid JWT_SECRET works."""
        settings = Settings(JWT_SECRET="test-secret-key-abc123")
        assert settings.JWT_SECRET == "test-secret-key-abc123"

    def test_config_jwt_secret_strong_succeeds(self):
        """Test that strong JWT_SECRET works."""
        strong_secret = "a" * 32  # 32 character secret
        settings = Settings(JWT_SECRET=strong_secret)
        assert settings.JWT_SECRET == strong_secret

    @patch("app.core.config.logger")
    def test_config_jwt_secret_empty_logs_critical(self, mock_logger):
        """Test that empty JWT_SECRET logs critical error."""
        with pytest.raises(ValueError):
            Settings(JWT_SECRET="")

        # Verify critical log was called
        mock_logger.critical.assert_called_once()
        call_args = mock_logger.critical.call_args[0][0]
        assert "JWT_SECRET is empty" in call_args
        assert "Set JWT_SECRET in .env file" in call_args


class TestCORSConfiguration:
    """Test CORS configuration validation."""

    def test_config_cors_origins_list_converts_to_string(self):
        """Test CORS_ORIGINS converts list to string."""
        settings = Settings(
            JWT_SECRET="test-secret",
            CORS_ORIGINS=["http://localhost:3000", "http://localhost:8080"],
        )
        assert isinstance(settings.CORS_ORIGINS, str)
        assert "http://localhost:3000" in settings.CORS_ORIGINS

    def test_config_cors_origins_string_parses_to_list(self):
        """Test get_cors_origins_list() parses string correctly."""
        settings = Settings(
            JWT_SECRET="test-secret",
            CORS_ORIGINS="http://localhost:3000,http://localhost:8080",
        )
        origins = settings.get_cors_origins_list()
        assert len(origins) == 2
        assert "http://localhost:3000" in origins
        assert "http://localhost:8080" in origins


class TestDatabaseConfiguration:
    """Test database configuration."""

    def test_config_database_url_custom_value_accepted(self):
        """Test DATABASE_URL can be configured with custom value."""
        db_url = "postgresql+asyncpg://user:pass@localhost:5432/testdb"
        settings = Settings(JWT_SECRET="test-secret", DATABASE_URL=db_url)
        assert settings.DATABASE_URL == db_url

    def test_config_old_database_url_none_accepted(self):
        """Test OLD_DATABASE_URL accepts None value."""
        # Create settings without specifying OLD_DATABASE_URL
        # Note: May be loaded from .env if present, so just check it's nullable
        settings = Settings(JWT_SECRET="test-secret", OLD_DATABASE_URL=None)
        assert settings.OLD_DATABASE_URL is None


class TestYAMLConfiguration:
    """Test YAML configuration loading."""

    def test_config_pagination_defaults_sensible_values(self):
        """Test pagination configuration has sensible defaults."""
        settings = Settings(JWT_SECRET="test-secret")
        assert settings.pagination.default_page_size == 20
        assert settings.pagination.max_page_size == 1000

    def test_config_vep_api_defaults_ensembl_url(self):
        """Test VEP API configuration has expected defaults."""
        settings = Settings(JWT_SECRET="test-secret")
        assert "ensembl.org" in settings.external_apis.vep.base_url
        assert settings.external_apis.vep.timeout_seconds > 0

    def test_config_pubmed_api_defaults_ncbi_url(self):
        """Test PubMed API configuration has expected defaults."""
        settings = Settings(JWT_SECRET="test-secret")
        assert "ncbi.nlm.nih.gov" in settings.external_apis.pubmed.base_url
        assert settings.external_apis.pubmed.timeout_seconds > 0

    def test_config_rate_limiting_defaults_positive_values(self):
        """Test rate limiting configuration has sensible defaults."""
        settings = Settings(JWT_SECRET="test-secret")
        assert settings.rate_limiting.api.requests_per_second > 0
        assert settings.rate_limiting.vep.requests_per_second > 0
        assert settings.rate_limiting.pubmed.requests_per_second_with_key > 0

    def test_config_legacy_properties_map_to_yaml(self):
        """Test legacy property aliases work for backward compatibility."""
        settings = Settings(JWT_SECRET="test-secret")
        # These legacy properties should map to YAML config
        assert settings.JWT_ALGORITHM == settings.security.jwt_algorithm
        assert (
            settings.ACCESS_TOKEN_EXPIRE_MINUTES
            == settings.security.access_token_expire_minutes
        )
        assert settings.VEP_API_BASE_URL == settings.external_apis.vep.base_url
