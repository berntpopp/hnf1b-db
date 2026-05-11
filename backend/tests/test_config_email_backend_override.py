"""Tests for EMAIL_BACKEND env override semantics (Wave 5c follow-up)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.core.config import EmailConfig, Settings, YamlConfig


def _build_settings_with_stub_yaml(
    *,
    env_override: str | None,
    yaml_backend: str,
    environment: str,
) -> Settings:
    """Build Settings with a stubbed YAML config (patched before construction).

    Validators run during Settings(...) construction, so the YAML stub must be
    in place via patching load_yaml_config before the call, not via post-hoc
    mutation of _yaml_config. See PR review for issue #287.
    """
    yaml_cfg = YamlConfig(email=EmailConfig(backend=yaml_backend))
    smtp_needed = (env_override or yaml_backend) == "smtp"

    kwargs: dict[str, object] = {
        "JWT_SECRET": "test-secret-key-abc123",
        "ADMIN_PASSWORD": "TestAdminPass!2026",
        "environment": environment,
        "AUTH_COOKIE_SECURE": environment != "development",
        "SMTP_HOST": "smtp.example.com" if smtp_needed else "",
        "SMTP_USERNAME": "user" if smtp_needed else "",
        "SMTP_PASSWORD": "pass" if smtp_needed else "",
    }
    if env_override is not None:
        kwargs["EMAIL_BACKEND"] = env_override

    with patch("app.core.config.load_yaml_config", return_value=yaml_cfg):
        return Settings(**kwargs)


def test_email_backend_env_overrides_yaml_console_in_production():
    """EMAIL_BACKEND=smtp must override yaml backend='console' in production."""
    settings = _build_settings_with_stub_yaml(
        env_override="smtp", yaml_backend="console", environment="production"
    )
    assert settings.EMAIL_BACKEND == "smtp"


def test_yaml_console_default_still_rejects_in_production_without_override():
    """Without EMAIL_BACKEND set, yaml 'console' default must still fail-closed."""
    with pytest.raises(ValueError, match="email.backend is 'console'"):
        _build_settings_with_stub_yaml(
            env_override=None, yaml_backend="console", environment="production"
        )


def test_yaml_smtp_default_without_smtp_host_also_fails_closed():
    """Direct YAML 'smtp' with no SMTP_HOST must fail (proves stub really overrides yaml)."""
    yaml_cfg = YamlConfig(email=EmailConfig(backend="smtp"))
    with pytest.raises(ValueError, match="SMTP_HOST"):
        with patch("app.core.config.load_yaml_config", return_value=yaml_cfg):
            Settings(
                JWT_SECRET="test-secret-key-abc123",
                ADMIN_PASSWORD="TestAdminPass!2026",
                environment="production",
                AUTH_COOKIE_SECURE=True,
                SMTP_HOST="",
            )


def test_email_backend_env_override_smtp_requires_smtp_host():
    """EMAIL_BACKEND=smtp without SMTP_HOST must fail-closed (validator runs after override)."""
    with pytest.raises(ValueError, match="SMTP_HOST"):
        Settings(
            JWT_SECRET="test-secret-key-abc123",
            ADMIN_PASSWORD="TestAdminPass!2026",
            environment="production",
            AUTH_COOKIE_SECURE=True,
            EMAIL_BACKEND="smtp",
            SMTP_HOST="",
        )


def test_dev_keeps_yaml_console_default_with_no_env_override():
    """Dev environment leaves yaml 'console' default in place; no override needed."""
    settings = _build_settings_with_stub_yaml(
        env_override=None, yaml_backend="console", environment="development"
    )
    assert settings.EMAIL_BACKEND is None


def test_resolved_email_backend_property_reflects_env_override():
    """Settings.resolved_email_backend must agree with both validator and runtime."""
    settings = _build_settings_with_stub_yaml(
        env_override="smtp", yaml_backend="console", environment="production"
    )
    assert settings.resolved_email_backend == "smtp"


def test_resolved_email_backend_property_falls_back_to_yaml():
    """When no env override, the property reflects the YAML value."""
    settings = _build_settings_with_stub_yaml(
        env_override=None, yaml_backend="console", environment="development"
    )
    assert settings.resolved_email_backend == "console"


def test_get_email_sender_honours_email_backend_env_override():
    """Regression: get_email_sender() must use the resolved backend, not YAML alone.

    Without this, a production deploy with EMAIL_BACKEND=smtp would pass
    validators but actually send via console — defeating fail-closed
    semantics (see PR #289 Copilot review).
    """
    from app.auth.email import (
        ConsoleEmailSender,
        SMTPEmailSender,
        get_email_sender,
    )
    from app.core import config as config_module

    settings = _build_settings_with_stub_yaml(
        env_override="smtp", yaml_backend="console", environment="production"
    )

    with (
        patch.object(config_module, "settings", settings),
        patch("app.auth.email.settings", settings),
    ):
        sender = get_email_sender()

    assert isinstance(sender, SMTPEmailSender)
    assert not isinstance(sender, ConsoleEmailSender)


def test_get_email_sender_uses_yaml_when_no_env_override():
    """No env override → factory uses the YAML default (console in dev)."""
    from app.auth.email import ConsoleEmailSender, get_email_sender
    from app.core import config as config_module

    settings = _build_settings_with_stub_yaml(
        env_override=None, yaml_backend="console", environment="development"
    )

    with (
        patch.object(config_module, "settings", settings),
        patch("app.auth.email.settings", settings),
    ):
        sender = get_email_sender()

    assert isinstance(sender, ConsoleEmailSender)
