"""Tests for SMTPEmailSender (Wave 6 Task 8)."""

from unittest.mock import AsyncMock, patch

import aiosmtplib
import pytest

from app.auth.email import (
    ConsoleEmailSender,
    SMTPEmailSender,
    get_email_sender,
)
from app.core.config import settings


@pytest.fixture
def smtp_settings(monkeypatch):
    """Flip settings into a minimal SMTP configuration for one test."""
    monkeypatch.setattr(settings.email, "backend", "smtp")
    monkeypatch.setattr(settings.email, "tls_mode", "starttls")
    monkeypatch.setattr(settings.email, "validate_certs", False)
    monkeypatch.setattr(settings.email, "timeout_seconds", 5)
    monkeypatch.setattr(settings.email, "use_credentials", True)
    monkeypatch.setattr(settings.email, "max_retries", 0)
    monkeypatch.setattr(settings.email, "retry_backoff_factor", 1.0)
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(settings, "SMTP_PORT", 587)
    monkeypatch.setattr(settings, "SMTP_USERNAME", "user@example.com")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "hunter2")
    return settings


def test_factory_returns_smtp_sender_when_backend_is_smtp(smtp_settings):
    """Factory returns SMTPEmailSender when email.backend is 'smtp'."""
    sender = get_email_sender()
    assert isinstance(sender, SMTPEmailSender)


def test_factory_returns_console_sender_when_backend_is_console(monkeypatch):
    """Factory still returns ConsoleEmailSender when email.backend is 'console'."""
    monkeypatch.setattr(settings.email, "backend", "console")
    sender = get_email_sender()
    assert isinstance(sender, ConsoleEmailSender)


async def test_smtp_sender_calls_aiosmtplib_with_expected_args(smtp_settings):
    """SMTPEmailSender.send() calls aiosmtplib.send with host/port/creds/TLS."""
    with patch("app.auth.email.aiosmtplib.send", new=AsyncMock()) as mock_send:
        sender = SMTPEmailSender()
        await sender.send(
            to="alice@example.org",
            subject="Reset your password",
            body_html="<p>Hi</p>",
        )

    assert mock_send.await_count == 1
    _, kwargs = mock_send.call_args
    assert kwargs["hostname"] == "smtp.example.com"
    assert kwargs["port"] == 587
    assert kwargs["username"] == "user@example.com"
    assert kwargs["password"] == "hunter2"
    assert kwargs["start_tls"] is True
    assert kwargs["use_tls"] is False
    assert kwargs["timeout"] == 5


async def test_smtp_sender_skips_auth_when_use_credentials_false(
    smtp_settings, monkeypatch
):
    """use_credentials=False passes None for username/password (for e.g. Mailpit)."""
    monkeypatch.setattr(settings.email, "use_credentials", False)
    with patch("app.auth.email.aiosmtplib.send", new=AsyncMock()) as mock_send:
        sender = SMTPEmailSender()
        await sender.send("a@b.com", "s", "<p>b</p>")

    _, kwargs = mock_send.call_args
    assert kwargs["username"] is None
    assert kwargs["password"] is None


async def test_smtp_sender_retries_on_transient_failure(smtp_settings, monkeypatch):
    """Transient SMTPException is retried up to max_retries and then succeeds."""
    monkeypatch.setattr(settings.email, "max_retries", 2)
    attempts = {"n": 0}

    async def flaky_send(*args, **kwargs):
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise aiosmtplib.SMTPException("transient")

    with (
        patch("app.auth.email.aiosmtplib.send", side_effect=flaky_send),
        patch("app.auth.email.asyncio.sleep", new=AsyncMock()),
    ):
        sender = SMTPEmailSender()
        await sender.send("a@b.com", "s", "<p>b</p>")

    assert attempts["n"] == 3


async def test_smtp_sender_raises_after_max_retries(smtp_settings, monkeypatch):
    """After (max_retries + 1) consecutive failures, the original SMTPException is raised."""
    monkeypatch.setattr(settings.email, "max_retries", 1)

    async def always_fail(*args, **kwargs):
        raise aiosmtplib.SMTPException("down")

    with (
        patch("app.auth.email.aiosmtplib.send", side_effect=always_fail),
        patch("app.auth.email.asyncio.sleep", new=AsyncMock()),
        pytest.raises(aiosmtplib.SMTPException),
    ):
        sender = SMTPEmailSender()
        await sender.send("a@b.com", "s", "<p>b</p>")


async def test_smtp_sender_does_not_retry_authentication_error(
    smtp_settings, monkeypatch
):
    """SMTPAuthenticationError is re-raised immediately without retry.

    Retrying AUTH failures against a real provider can trip rate
    limiters or lock the account; the sender must bail on the first
    failure even if max_retries is high.
    """
    monkeypatch.setattr(settings.email, "max_retries", 5)
    attempts = {"n": 0}

    async def always_auth_fail(*args, **kwargs):
        attempts["n"] += 1
        raise aiosmtplib.SMTPAuthenticationError(535, "bad creds")

    with (
        patch("app.auth.email.aiosmtplib.send", side_effect=always_auth_fail),
        patch("app.auth.email.asyncio.sleep", new=AsyncMock()) as mock_sleep,
        pytest.raises(aiosmtplib.SMTPAuthenticationError),
    ):
        sender = SMTPEmailSender()
        await sender.send("a@b.com", "s", "<p>b</p>")

    assert attempts["n"] == 1
    mock_sleep.assert_not_called()


async def test_smtp_sender_does_not_retry_recipient_refused(smtp_settings, monkeypatch):
    """SMTPRecipientRefused is re-raised immediately without retry.

    A rejected recipient is a permanent error — retrying will just
    rack up bounces and hurt sender reputation with providers like
    SendGrid / SES.
    """
    monkeypatch.setattr(settings.email, "max_retries", 3)
    attempts = {"n": 0}

    async def always_reject(*args, **kwargs):
        attempts["n"] += 1
        raise aiosmtplib.SMTPRecipientRefused(550, "no such user", "a@b.com")

    with (
        patch("app.auth.email.aiosmtplib.send", side_effect=always_reject),
        patch("app.auth.email.asyncio.sleep", new=AsyncMock()) as mock_sleep,
        pytest.raises(aiosmtplib.SMTPRecipientRefused),
    ):
        sender = SMTPEmailSender()
        await sender.send("a@b.com", "s", "<p>b</p>")

    assert attempts["n"] == 1
    mock_sleep.assert_not_called()


def test_factory_raises_on_unknown_backend(monkeypatch):
    """Unknown backend values raise ValueError (defensive — not silently fallback)."""
    monkeypatch.setattr(settings.email, "backend", "carrier-pigeon")
    with pytest.raises(ValueError, match="Unknown email backend"):
        get_email_sender()
