"""Email dispatch for identity lifecycle flows.

Wave 5c: shipped ConsoleEmailSender (logs to structured logger).
Wave 6: adds SMTPEmailSender over aiosmtplib. The endpoint code
never changed — they depend on the EmailSender protocol and the
get_email_sender() factory picks a concrete backend from
settings.email.backend.
"""

import asyncio
import logging
import re
from email.message import EmailMessage
from typing import Protocol, runtime_checkable

import aiosmtplib

from app.core.config import settings

logger = logging.getLogger(__name__)


@runtime_checkable
class EmailSender(Protocol):
    """Protocol for email dispatch backends."""

    async def send(self, to: str, subject: str, body_html: str) -> None:
        """Send an email."""
        ...


class ConsoleEmailSender:
    """Logs emails to the structured logger instead of sending them.

    Sole implementation in Wave 5c. All identity endpoints depend on
    the EmailSender protocol, so Wave 6 can slot in SMTPEmailSender
    via get_email_sender() without changing any endpoint.
    """

    async def send(self, to: str, subject: str, body_html: str) -> None:
        """Log the email content to the structured logger."""
        urls = re.findall(r'https?://[^\s<>"\']+', body_html)
        url_line = f" | URL: {urls[0]}" if urls else ""

        logger.info(
            "EMAIL [console backend] To: %s | Subject: %s%s",
            to,
            subject,
            url_line,
        )
        logger.debug("EMAIL body:\n%s", body_html)


# Permanent SMTP failures that MUST NOT be retried. Retrying these
# risks provider-side rate-limiting or temporary account lockouts
# (e.g. Gmail will soft-block the sender after repeated AUTH failures
# from the same IP, SendGrid counts recipient-refused as a bounce).
# The generic ``SMTPException`` covers transient errors (connect /
# timeout / throttling) and is the only family retried below.
_PERMANENT_SMTP_ERRORS: tuple[type[BaseException], ...] = (
    aiosmtplib.SMTPAuthenticationError,
    aiosmtplib.SMTPRecipientRefused,
    aiosmtplib.SMTPRecipientsRefused,
    aiosmtplib.SMTPSenderRefused,
)


class SMTPEmailSender:
    """Send emails over SMTP using aiosmtplib.

    Reads all host/port/credentials from ``settings`` at send time so
    tests can monkeypatch the config between sends. The send path
    honours:

    - ``settings.email.tls_mode`` — ``starttls`` / ``ssl`` / ``none``
    - ``settings.email.validate_certs``
    - ``settings.email.timeout_seconds``
    - ``settings.email.use_credentials`` (skip AUTH for e.g. Mailpit)
    - ``settings.email.max_retries`` + ``retry_backoff_factor`` for
      transient SMTP errors. Auth / recipient-refused / sender-refused
      failures are re-raised immediately without retry to avoid
      provider-side rate-limiting or account lockouts. Retries wait
      ``backoff_factor ** attempt`` seconds between attempts.
    """

    async def send(self, to: str, subject: str, body_html: str) -> None:
        """Send one HTML email, retrying only on transient SMTP failures."""
        email_cfg = settings.email

        message = EmailMessage()
        message["From"] = f"{email_cfg.from_name} <{email_cfg.from_address}>"
        message["To"] = to
        message["Subject"] = subject
        message.set_content(
            "This message requires an HTML-capable email client.",
        )
        message.add_alternative(body_html, subtype="html")

        tls_mode = email_cfg.tls_mode
        use_tls = tls_mode == "ssl"
        start_tls = tls_mode == "starttls"

        username = settings.SMTP_USERNAME if email_cfg.use_credentials else None
        password = settings.SMTP_PASSWORD if email_cfg.use_credentials else None

        last_exc: Exception | None = None
        for attempt in range(email_cfg.max_retries + 1):
            try:
                await aiosmtplib.send(
                    message,
                    hostname=settings.SMTP_HOST,
                    port=settings.SMTP_PORT,
                    username=username,
                    password=password,
                    use_tls=use_tls,
                    start_tls=start_tls,
                    validate_certs=email_cfg.validate_certs,
                    timeout=email_cfg.timeout_seconds,
                )
                logger.info(
                    "EMAIL [smtp backend] To: %s | Subject: %s | host=%s:%s",
                    to,
                    subject,
                    settings.SMTP_HOST,
                    settings.SMTP_PORT,
                )
                return
            except _PERMANENT_SMTP_ERRORS as exc:
                # Never retry — raising immediately protects us from
                # provider lockouts on misconfigured credentials or
                # bad recipient lists.
                logger.error(
                    "SMTP send failed permanently (no retry): %s: %s",
                    type(exc).__name__,
                    exc,
                )
                raise
            except aiosmtplib.SMTPException as exc:
                last_exc = exc
                if attempt >= email_cfg.max_retries:
                    break
                delay = email_cfg.retry_backoff_factor**attempt
                logger.warning(
                    "SMTP send attempt %d/%d failed (%s); retrying in %.1fs",
                    attempt + 1,
                    email_cfg.max_retries + 1,
                    exc,
                    delay,
                )
                await asyncio.sleep(delay)

        logger.error(
            "SMTP send permanently failed after %d attempts: %s",
            email_cfg.max_retries + 1,
            last_exc,
        )
        # Loop only reaches here via break, which only runs when
        # last_exc was set by the transient-except branch; mypy /
        # pylint can't see that.
        assert last_exc is not None  # noqa: S101
        raise last_exc


def get_email_sender() -> EmailSender:
    """Return the configured email sender.

    Reads ``email.backend`` from ``config.yaml``:

    - ``"console"`` → :class:`ConsoleEmailSender` (default)
    - ``"smtp"`` → :class:`SMTPEmailSender` (Wave 6)
    """
    backend = settings.email.backend
    if backend == "console":
        return ConsoleEmailSender()
    if backend == "smtp":
        return SMTPEmailSender()
    raise ValueError(f"Unknown email backend: {backend!r}")
