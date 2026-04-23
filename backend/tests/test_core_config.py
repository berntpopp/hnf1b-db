"""Tests for backend/app/core/config.py startup validation.

Exercises the field_validators for JWT_SECRET and ADMIN_PASSWORD that
cause the application to fail fast if critical secrets are unset.
"""

import importlib

import pytest
from pydantic import ValidationError

BASE_ENV = {
    "DATABASE_URL": "postgresql+asyncpg://test:test@localhost:5433/test",
}


def seed_safe_import_env(monkeypatch):
    """Seed a safe ambient env before reloading app.core.config."""
    for k, v in BASE_ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("JWT_SECRET", "0" * 64)
    monkeypatch.setenv("ADMIN_PASSWORD", "validpassword")
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "true")


def load_config_module():
    """Reload app.core.config so settings construct from current test env."""
    config_module = importlib.import_module("app.core.config")
    return importlib.reload(config_module)


def build_yaml_config(config_module, *, email_backend: str = "console"):
    """Build a minimal YAML config override for settings tests."""
    return config_module.YamlConfig(
        email=config_module.EmailConfig(backend=email_backend)
    )


class TestJwtSecretValidation:
    """Validate JWT_SECRET field_validator fail-fast behavior."""

    def test_empty_jwt_secret_raises(self, monkeypatch):
        """Empty JWT_SECRET must raise ValidationError."""
        seed_safe_import_env(monkeypatch)
        Settings = load_config_module().Settings
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                _env_file=None,
                DATABASE_URL=BASE_ENV["DATABASE_URL"],
                JWT_SECRET="",
                ADMIN_PASSWORD="validpassword",
            )
        assert "JWT_SECRET" in str(exc_info.value)

    def test_whitespace_jwt_secret_raises(self, monkeypatch):
        """Whitespace-only JWT_SECRET must raise ValidationError."""
        seed_safe_import_env(monkeypatch)
        Settings = load_config_module().Settings
        with pytest.raises(ValidationError):
            Settings(
                _env_file=None,
                DATABASE_URL=BASE_ENV["DATABASE_URL"],
                JWT_SECRET="   ",
                ADMIN_PASSWORD="validpassword",
            )

    def test_valid_jwt_secret_accepted(self, monkeypatch):
        """A non-empty JWT_SECRET must allow Settings to construct."""
        seed_safe_import_env(monkeypatch)
        Settings = load_config_module().Settings
        s = Settings(_env_file=None)
        assert s.JWT_SECRET == "0" * 64


class TestAdminPasswordValidation:
    """Validate ADMIN_PASSWORD field_validator fail-fast behavior."""

    def test_empty_admin_password_raises(self, monkeypatch):
        """Empty ADMIN_PASSWORD must raise ValidationError."""
        seed_safe_import_env(monkeypatch)
        Settings = load_config_module().Settings
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                _env_file=None,
                DATABASE_URL=BASE_ENV["DATABASE_URL"],
                JWT_SECRET="0" * 64,
                ADMIN_PASSWORD="",
            )
        assert "ADMIN_PASSWORD" in str(exc_info.value)

    def test_whitespace_admin_password_raises(self, monkeypatch):
        """Whitespace-only ADMIN_PASSWORD must raise ValidationError."""
        seed_safe_import_env(monkeypatch)
        Settings = load_config_module().Settings
        with pytest.raises(ValidationError):
            Settings(
                _env_file=None,
                DATABASE_URL=BASE_ENV["DATABASE_URL"],
                JWT_SECRET="0" * 64,
                ADMIN_PASSWORD="   ",
            )


class TestHpoTermsConfig:
    """Smoke-check HPO terms config accessibility via Settings."""

    def test_hpo_terms_section_accessible(self, monkeypatch):
        """hpo_terms property should expose the YAML HPOTermsConfig model."""
        seed_safe_import_env(monkeypatch)
        Settings = load_config_module().Settings
        s = Settings(_env_file=None)
        # hpo_terms is exposed as a property that proxies to yaml.hpo_terms
        assert hasattr(s, "hpo_terms")
        # Smoke-check that the config contains expected known HPO constants
        assert isinstance(s.hpo_terms.cakut, list)
        assert "HP:0000003" in s.hpo_terms.cakut
        assert s.hpo_terms.mody == "HP:0004904"

    def test_scalar_aliases_match_list_forms(self, monkeypatch):
        """Scalar HPO aliases must stay in sync with their list-shaped siblings.

        Wave 3 added scalar aliases (``ckd_stage_4``, ``ckd_stage_5``,
        ``chronic_kidney_disease``) alongside existing list-shaped
        constants (``kidney_failure``, ``stage_5_ckd``, ``ckd_stages``).
        This drift-prevention test asserts the scalars still match the
        list elements they alias, so a future edit that updates one form
        but not the other fails fast instead of introducing silent config
        divergence.
        """
        seed_safe_import_env(monkeypatch)
        Settings = load_config_module().Settings
        s = Settings(_env_file=None)

        # stage_5_ckd is a single-element list holding the ESRD HPO ID
        assert s.hpo_terms.stage_5_ckd == [s.hpo_terms.ckd_stage_5]
        # kidney_failure is [Stage 4, Stage 5/ESRD]
        assert s.hpo_terms.kidney_failure == [
            s.hpo_terms.ckd_stage_4,
            s.hpo_terms.ckd_stage_5,
        ]
        # chronic_kidney_disease (unspecified) is the first CKD term in ckd_stages
        assert s.hpo_terms.ckd_stages[0] == s.hpo_terms.chronic_kidney_disease
        # ckd_stage_4 and ckd_stage_5 both appear in ckd_stages
        assert s.hpo_terms.ckd_stage_4 in s.hpo_terms.ckd_stages
        assert s.hpo_terms.ckd_stage_5 in s.hpo_terms.ckd_stages
        # All three scalars are canonical HPO IDs
        for term in (
            s.hpo_terms.chronic_kidney_disease,
            s.hpo_terms.ckd_stage_4,
            s.hpo_terms.ckd_stage_5,
        ):
            assert term.startswith("HP:")
            assert len(term) == 10  # "HP:" + 7 digits


class TestProductionEmailAndCookieValidation:
    """Validate fail-closed startup rules for email and auth cookies."""

    def test_production_console_email_raises(self, monkeypatch):
        """Production must reject console email delivery."""
        seed_safe_import_env(monkeypatch)
        config_module = load_config_module()
        monkeypatch.setattr(
            config_module,
            "load_yaml_config",
            lambda: build_yaml_config(config_module, email_backend="console"),
        )

        with pytest.raises(ValidationError, match="email.backend"):
            config_module.Settings(
                _env_file=None,
                environment="production",
                AUTH_COOKIE_SECURE=True,
            )

    @pytest.mark.parametrize("environment", ["staging", "production"])
    def test_staging_and_production_insecure_auth_cookies_raise(
        self, monkeypatch, environment
    ):
        """Staging-like environments must reject insecure auth cookies."""
        seed_safe_import_env(monkeypatch)
        config_module = load_config_module()
        monkeypatch.setattr(
            config_module,
            "load_yaml_config",
            lambda: build_yaml_config(config_module, email_backend="smtp"),
        )
        monkeypatch.setenv("SMTP_HOST", "smtp.example.test")
        monkeypatch.setenv("SMTP_USERNAME", "user")
        monkeypatch.setenv("SMTP_PASSWORD", "password")

        with pytest.raises(ValidationError, match="AUTH_COOKIE_SECURE"):
            config_module.Settings(
                _env_file=None,
                environment=environment,
                AUTH_COOKIE_SECURE=False,
            )

    def test_development_console_email_allowed(self, monkeypatch):
        """Development may use console email delivery."""
        seed_safe_import_env(monkeypatch)
        config_module = load_config_module()
        monkeypatch.setattr(
            config_module,
            "load_yaml_config",
            lambda: build_yaml_config(config_module, email_backend="console"),
        )

        s = config_module.Settings(
            _env_file=None,
            DATABASE_URL=BASE_ENV["DATABASE_URL"],
            JWT_SECRET="0" * 64,
            ADMIN_PASSWORD="validpassword",
            environment="development",
            AUTH_COOKIE_SECURE=False,
        )

        assert s.environment == "development"
        assert s.email.backend == "console"

    def test_development_insecure_auth_cookies_allowed(self, monkeypatch):
        """Development may keep insecure auth cookies."""
        seed_safe_import_env(monkeypatch)
        config_module = load_config_module()
        monkeypatch.setattr(
            config_module,
            "load_yaml_config",
            lambda: build_yaml_config(config_module, email_backend="smtp"),
        )

        s = config_module.Settings(
            _env_file=None,
            DATABASE_URL=BASE_ENV["DATABASE_URL"],
            JWT_SECRET="0" * 64,
            ADMIN_PASSWORD="validpassword",
            environment="development",
            AUTH_COOKIE_SECURE=False,
            SMTP_HOST="smtp.example.test",
            SMTP_USERNAME="user",
            SMTP_PASSWORD="password",
        )

        assert s.environment == "development"
        assert s.AUTH_COOKIE_SECURE is False
