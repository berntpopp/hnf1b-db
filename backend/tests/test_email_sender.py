"""Tests for EmailSender protocol and ConsoleEmailSender."""

import logging

import pytest

from app.auth.email import ConsoleEmailSender, EmailSender, get_email_sender


def test_console_email_sender_satisfies_protocol():
    """ConsoleEmailSender implements the EmailSender protocol."""
    sender = ConsoleEmailSender()
    assert isinstance(sender, EmailSender)


@pytest.mark.asyncio
async def test_console_email_sender_logs_email(caplog):
    """ConsoleEmailSender writes email details to the structured logger."""
    sender = ConsoleEmailSender()
    with caplog.at_level(logging.INFO, logger="app.auth.email"):
        await sender.send(
            to="user@example.com",
            subject="Reset your password",
            body_html="<p>Click <a href='http://localhost/reset/abc123'>here</a></p>",
        )

    assert "user@example.com" in caplog.text
    assert "Reset your password" in caplog.text
    assert "http://localhost/reset/abc123" in caplog.text


@pytest.mark.asyncio
async def test_console_email_sender_includes_token_url(caplog):
    """ConsoleEmailSender extracts and highlights the token URL."""
    sender = ConsoleEmailSender()
    with caplog.at_level(logging.INFO, logger="app.auth.email"):
        await sender.send(
            to="invited@example.com",
            subject="You've been invited",
            body_html="<p>Accept: http://localhost:5173/accept-invite/tok_abc</p>",
        )

    assert "invited@example.com" in caplog.text
    assert "tok_abc" in caplog.text


def test_get_email_sender_returns_console_by_default():
    """Default config returns ConsoleEmailSender."""
    sender = get_email_sender()
    assert isinstance(sender, ConsoleEmailSender)
