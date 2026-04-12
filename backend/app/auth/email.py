"""Email dispatch for identity lifecycle flows.

Wave 5c: ships ConsoleEmailSender only (logs to structured logger).
Wave 6 will add SMTPEmailSender without touching endpoint code.
"""

import logging
import re
from typing import Protocol, runtime_checkable

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


def get_email_sender() -> EmailSender:
    """Return the configured email sender.

    Reads email.backend from config.yaml:
    - "console" -> ConsoleEmailSender (default)
    - "smtp" -> NotImplementedError (Wave 6)
    """
    backend = settings.email.backend
    if backend == "console":
        return ConsoleEmailSender()
    if backend == "smtp":
        raise NotImplementedError(
            "SMTPEmailSender is not yet implemented. "
            "Set email.backend: 'console' in config.yaml, "
            "or wait for Wave 6."
        )
    raise ValueError(f"Unknown email backend: {backend!r}")
