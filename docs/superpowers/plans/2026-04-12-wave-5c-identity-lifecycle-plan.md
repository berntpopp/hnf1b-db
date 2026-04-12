# Wave 5c — Identity Lifecycle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship credential-token-based identity flows (invite, password reset, email verification) with full SMTP config plumbing ready for Wave 6.

**Architecture:** New `credential_tokens` table stores SHA-256 hashed single-use tokens. An `EmailSender` protocol with `ConsoleEmailSender` dispatches token URLs to logs. A `RateLimiter` FastAPI dependency guards anonymous endpoints via Redis-backed counters. Frontend adds 4 anonymous views + an invite dialog on admin.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async, Alembic, pwdlib (Argon2id), Redis cache, Vue 3 Composition API, Vuetify 3, Vitest

**Design spec:** `docs/superpowers/specs/2026-04-12-wave-5c-identity-lifecycle-design.md`
**Scope doc:** `docs/superpowers/plans/2026-04-11-wave-5-scope.md` §4.3
**Branch:** `chore/wave-5c-identity-lifecycle`
**Commit budget:** ≤13
**Entry state:** main at `c5ecb1f`, 1090 backend tests, 292 frontend tests, 14 HTTP baselines

---

## File Structure

### New files

| File | Responsibility |
|------|----------------|
| `backend/app/models/credential_token.py` | SQLAlchemy ORM model for `credential_tokens` table |
| `backend/alembic/versions/<hex>_credential_tokens.py` | Alembic migration (auto-generated) |
| `backend/app/auth/credential_tokens.py` | Token repository: create, verify-and-consume, invalidate |
| `backend/app/auth/email.py` | `EmailSender` protocol + `ConsoleEmailSender` + `get_email_sender` DI |
| `backend/app/auth/rate_limit.py` | `RateLimiter` FastAPI dependency for per-endpoint rate limiting |
| `backend/tests/test_credential_tokens.py` | Token repository unit tests |
| `backend/tests/test_email_sender.py` | EmailSender protocol + ConsoleEmailSender tests |
| `backend/tests/test_auth_invite.py` | Invite endpoint integration tests |
| `backend/tests/test_auth_password_reset.py` | Password reset endpoint tests |
| `backend/tests/test_auth_email_verify.py` | Email verify + resend + auto-dispatch tests |
| `backend/tests/test_auth_rate_limits_wave5c.py` | Rate limiter integration tests |
| `backend/tests/test_register_endpoint_absent.py` | Invite-only negative test |
| `frontend/src/views/ForgotPassword.vue` | Email form, submits reset request, dev-only token banner |
| `frontend/src/views/ResetPassword.vue` | New password form, consumes reset token from route |
| `frontend/src/views/AcceptInvite.vue` | Username + full name + password form, consumes invite token |
| `frontend/src/views/VerifyEmail.vue` | Auto-consumes verify token on mount |
| `frontend/src/components/admin/UserInviteDialog.vue` | Admin invite dialog (email + role) |
| `frontend/tests/unit/views/ForgotPassword.spec.js` | ForgotPassword view tests |
| `frontend/tests/unit/views/ResetPassword.spec.js` | ResetPassword view tests |
| `frontend/tests/unit/views/AcceptInvite.spec.js` | AcceptInvite view tests |
| `frontend/tests/unit/views/VerifyEmail.spec.js` | VerifyEmail view tests |

### Modified files

| File | What changes |
|------|-------------|
| `backend/app/core/config.py` | Add `EmailConfig` model, SMTP env vars, startup validators, `email` property |
| `backend/app/schemas/auth.py` | Add 6 new request/response schemas for identity endpoints |
| `backend/app/api/auth_endpoints.py` | Add 6 new endpoints (invite, accept, reset-request, reset-confirm, verify, verify-resend); modify `create_user` to auto-dispatch verify email |
| `backend/app/auth/__init__.py` | Re-export new modules |
| `backend/app/models/__init__.py` | Import CredentialToken (if exists) |
| `backend/alembic/env.py` | Import CredentialToken model |
| `backend/.env.example` | Add SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD |
| `backend/config.yaml` | Add `email` section |
| `backend/tests/conftest.py` | Add `credential_tokens` to `_MUTABLE_TABLES` |
| `frontend/src/api/domain/auth.js` | Add 6 new API functions |
| `frontend/src/router/index.js` | Add 4 new anonymous routes |
| `frontend/src/views/Login.vue` | Wire forgot-password link |
| `frontend/src/views/AdminUsers.vue` | Add Invite User button + dialog |

---

## Task 1: `credential_tokens` Alembic migration + ORM model

**Commit message:** `feat(db): add credential_tokens table for identity lifecycle tokens`

**Files:**
- Create: `backend/app/models/credential_token.py`
- Create: `backend/alembic/versions/<hex>_credential_tokens.py` (auto-generated)
- Modify: `backend/alembic/env.py` (add model import)
- Modify: `backend/tests/conftest.py` (add to mutable tables)

- [ ] **Step 1: Create the CredentialToken model**

Create `backend/app/models/credential_token.py`:

```python
"""Credential token model for identity lifecycle flows.

Stores SHA-256 hashed single-use tokens for invite, password reset,
and email verification. Raw tokens are never persisted.
"""

from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CredentialToken(Base):
    """Single-use credential token for invite, reset, and verify flows.

    Attributes:
        id: Primary key
        user_id: FK to users.id (NULL for invite tokens — user doesn't exist yet)
        purpose: Token purpose: 'reset', 'invite', 'verify'
        token_sha256: SHA-256 hex hash of the raw token (unique, indexed)
        email: Email address bound at creation time
        expires_at: Expiration timestamp (default: created_at + 24h)
        used_at: Consumption timestamp (NULL = unused)
        metadata_: Purpose-specific data (e.g. {"role": "curator"} for invites)
        created_at: Creation timestamp
    """

    __tablename__ = "credential_tokens"
    __table_args__ = (
        CheckConstraint(
            "purpose IN ('reset', 'invite', 'verify')",
            name="ck_credential_tokens_purpose",
        ),
        Index("ix_credential_tokens_email_purpose", "email", "purpose"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=True
    )
    purpose: Mapped[str] = mapped_column(String(10), nullable=False)
    token_sha256: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    metadata_: Mapped[dict | None] = mapped_column(
        "metadata", JSONB, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
```

- [ ] **Step 2: Add model import to alembic env.py**

In `backend/alembic/env.py`, add the import alongside the existing model imports:

```python
from app.models.credential_token import CredentialToken  # noqa: F401
```

Add after the existing `from app.models.user import User` line.

- [ ] **Step 3: Add credential_tokens to test conftest mutable tables**

In `backend/tests/conftest.py`, add `"credential_tokens"` to `_MUTABLE_TABLES` — **before** `"users"` (FK dependency order: children before parents):

```python
_MUTABLE_TABLES: tuple[str, ...] = (
    "credential_tokens",
    "phenopacket_audit",
    "phenopackets",
    "variant_annotations",
    "publication_metadata",
    "users",
)
```

- [ ] **Step 4: Generate Alembic migration**

```bash
cd backend
uv run alembic revision --autogenerate -m "add credential_tokens table"
```

Expected: Creates a new migration file in `backend/alembic/versions/`.

- [ ] **Step 5: Review the auto-generated migration**

Open the generated file and verify it contains:
- `op.create_table("credential_tokens", ...)` with all columns
- The CHECK constraint for purpose
- The composite index on (email, purpose)
- A `downgrade()` that drops the table

If the `include_object` filter in `env.py` excludes `credential_tokens`, it won't appear. Verify the filter only excludes the known non-ORM tables.

- [ ] **Step 6: Apply the migration**

```bash
cd backend
uv run alembic upgrade head
```

Expected: Migration applies cleanly.

- [ ] **Step 7: Test the downgrade**

```bash
cd backend
uv run alembic downgrade -1
uv run alembic upgrade head
```

Expected: Both directions work cleanly.

- [ ] **Step 8: Run backend tests to verify no regressions**

```bash
cd backend
make test
```

Expected: 1090 tests pass (same as entry).

- [ ] **Step 9: Commit**

```bash
git add backend/app/models/credential_token.py backend/alembic/versions/*credential_tokens*.py backend/alembic/env.py backend/tests/conftest.py
git commit -m "feat(db): add credential_tokens table for identity lifecycle tokens"
```

---

## Task 2: Email config infrastructure

**Commit message:** `feat(config): add SMTP env vars and email config section`

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `backend/.env.example`
- Modify: `backend/config.yaml`

- [ ] **Step 1: Add EmailConfig model to config.py**

Add after the `SecurityConfig` class in `backend/app/core/config.py`:

```python
class EmailConfig(BaseModel):
    """Email delivery configuration (non-secret behavioral settings)."""

    backend: Literal["console", "smtp"] = "console"
    from_address: str = "noreply@hnf1b-db.org"
    from_name: str = "HNF1B Database"
    tls_mode: Literal["starttls", "ssl", "none"] = "starttls"
    validate_certs: bool = True
    timeout_seconds: int = 30
    use_credentials: bool = True
    max_retries: int = 3
    retry_backoff_factor: float = 2.0
```

- [ ] **Step 2: Add email to YamlConfig**

In the `YamlConfig` class, add:

```python
email: EmailConfig = EmailConfig()
```

- [ ] **Step 3: Add SMTP env vars to Settings**

In the `Settings` class, add after the `REDIS_URL` line:

```python
# SMTP credentials (for email delivery)
SMTP_HOST: str = ""
SMTP_PORT: int = 587
SMTP_USERNAME: str = ""
SMTP_PASSWORD: str = ""
```

- [ ] **Step 4: Add startup validators**

Add a new model validator to `Settings`, after `_refuse_dev_auth_in_prod`:

```python
@model_validator(mode="after")
def _validate_smtp_config(self) -> "Settings":
    """Fail fast if email backend is smtp but SMTP_HOST is missing."""
    email_cfg = self.yaml.email
    if email_cfg.backend == "smtp":
        if not self.SMTP_HOST or self.SMTP_HOST.strip() == "":
            raise ValueError(
                "REFUSING TO START: email.backend is 'smtp' but SMTP_HOST "
                "is empty. Set SMTP_HOST in .env or switch to "
                "email.backend: 'console' in config.yaml."
            )
        if email_cfg.use_credentials:
            if not self.SMTP_USERNAME or not self.SMTP_PASSWORD:
                raise ValueError(
                    "REFUSING TO START: email.backend is 'smtp' with "
                    "use_credentials: true, but SMTP_USERNAME or "
                    "SMTP_PASSWORD is empty. Set them in .env or set "
                    "email.use_credentials: false in config.yaml."
                )
    if email_cfg.tls_mode == "none":
        logger.critical(
            "EMAIL TLS IS DISABLED (email.tls_mode: 'none'). "
            "Emails will be sent unencrypted. This is only safe "
            "for trusted internal relays."
        )
    return self
```

- [ ] **Step 5: Add email convenience property**

In the `Settings` class convenience accessors section:

```python
@property
def email(self) -> EmailConfig:
    """Access email configuration."""
    return self.yaml.email
```

- [ ] **Step 6: Update .env.example**

Add to `backend/.env.example`:

```bash
# ── Email / SMTP Configuration ──
# Required only when config.yaml has email.backend: "smtp"
# For console/log mode (default), these can remain empty.
#
# SendGrid:  SMTP_HOST=smtp.sendgrid.net  SMTP_USERNAME=apikey  SMTP_PASSWORD=<your-api-key>
# Mailgun:   SMTP_HOST=smtp.mailgun.org   SMTP_USERNAME=postmaster@yourdomain.com
# AWS SES:   SMTP_HOST=email-smtp.us-east-1.amazonaws.com  (use IAM SMTP credentials)
SMTP_HOST=
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
```

- [ ] **Step 7: Update config.yaml**

Add to `backend/config.yaml`:

```yaml
# Email delivery — "console" logs token URLs to stdout (dev default);
# "smtp" sends real emails (requires SMTP_* env vars in .env).
email:
  backend: "console"
  from_address: "noreply@hnf1b-db.org"
  from_name: "HNF1B Database"
  tls_mode: "starttls"
  validate_certs: true
  timeout_seconds: 30
  use_credentials: true
  max_retries: 3
  retry_backoff_factor: 2.0
```

- [ ] **Step 8: Run backend tests**

```bash
cd backend
make test
```

Expected: 1090 tests pass. The validator only fires when `email.backend == "smtp"`, and the default is `"console"`.

- [ ] **Step 9: Commit**

```bash
git add backend/app/core/config.py backend/.env.example backend/config.yaml
git commit -m "feat(config): add SMTP env vars and email config section"
```

---

## Task 3: EmailSender protocol + ConsoleEmailSender

**Commit message:** `feat(auth): add EmailSender protocol with ConsoleEmailSender`

**Files:**
- Create: `backend/app/auth/email.py`
- Create: `backend/tests/test_email_sender.py`
- Modify: `backend/app/auth/__init__.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_email_sender.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend
uv run pytest tests/test_email_sender.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.auth.email'`

- [ ] **Step 3: Implement EmailSender protocol and ConsoleEmailSender**

Create `backend/app/auth/email.py`:

```python
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
        """Send an email.

        Args:
            to: Recipient email address
            subject: Email subject line
            body_html: HTML body content
        """
        ...


class ConsoleEmailSender:
    """Logs emails to the structured logger instead of sending them.

    This is the sole implementation in Wave 5c. All identity endpoints
    depend on the EmailSender protocol, so a Wave 6 SMTPEmailSender
    can slot in via get_email_sender() without changing any endpoint.
    """

    async def send(self, to: str, subject: str, body_html: str) -> None:
        """Log the email content to the structured logger."""
        # Extract URLs from HTML for easy copy-paste in dev
        urls = re.findall(r'https?://[^\s<>"\']+', body_html)
        url_line = f" | URL: {urls[0]}" if urls else ""

        logger.info(
            "EMAIL [console backend] To: %s | Subject: %s%s",
            to,
            subject,
            url_line,
        )
        logger.debug(
            "EMAIL body:\n%s",
            body_html,
        )


def get_email_sender() -> EmailSender:
    """Return the configured email sender.

    Reads email.backend from config.yaml:
    - "console" → ConsoleEmailSender (default, logs to stdout)
    - "smtp" → raises NotImplementedError (Wave 6)
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
```

- [ ] **Step 4: Update auth __init__.py**

Add to `backend/app/auth/__init__.py`:

```python
from app.auth.email import ConsoleEmailSender, EmailSender, get_email_sender
```

And add to `__all__`:

```python
    # Email
    "EmailSender",
    "ConsoleEmailSender",
    "get_email_sender",
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd backend
uv run pytest tests/test_email_sender.py -v
```

Expected: 4 passed.

- [ ] **Step 6: Run full backend suite**

```bash
cd backend
make test
```

Expected: 1090 + 4 = ~1094 passing.

- [ ] **Step 7: Commit**

```bash
git add backend/app/auth/email.py backend/tests/test_email_sender.py backend/app/auth/__init__.py
git commit -m "feat(auth): add EmailSender protocol with ConsoleEmailSender"
```

---

## Task 4: RateLimiter dependency

**Commit message:** `feat(auth): add per-endpoint RateLimiter dependency`

**Files:**
- Create: `backend/app/auth/rate_limit.py`
- Create: `backend/tests/test_auth_rate_limits_wave5c.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_auth_rate_limits_wave5c.py`:

```python
"""Tests for per-endpoint RateLimiter dependency.

Verifies count-and-reject logic (Nth+1 returns 429 + Retry-After).
Does NOT verify exact window expiry timing — see design spec §6 for
the acknowledged Redis vs in-memory parity gap.
"""

import pytest

from app.auth.rate_limit import RateLimiter
from app.core.cache import cache


@pytest.fixture(autouse=True)
def _clear_cache():
    """Clear cache counters before each test."""
    cache.use_fallback_only()
    cache.clear_fallback()
    yield
    cache.clear_fallback()


@pytest.mark.asyncio
async def test_rate_limiter_allows_within_limit(async_client, admin_headers):
    """Requests within limit succeed."""
    # This tests through an actual endpoint that uses the rate limiter.
    # We'll test the RateLimiter class directly here instead.
    limiter = RateLimiter("test-allow", max_requests=3, window_seconds=3600)

    # Simulate 3 requests (within limit)
    from unittest.mock import AsyncMock, MagicMock

    for _ in range(3):
        request = MagicMock()
        request.client.host = "127.0.0.1"
        await limiter(request)  # Should not raise


@pytest.mark.asyncio
async def test_rate_limiter_rejects_over_limit():
    """Request exceeding limit gets 429 with Retry-After header."""
    from fastapi import HTTPException
    from unittest.mock import MagicMock

    limiter = RateLimiter("test-reject", max_requests=2, window_seconds=3600)
    request = MagicMock()
    request.client.host = "127.0.0.1"

    # Use up the limit
    await limiter(request)
    await limiter(request)

    # Third request should fail
    with pytest.raises(HTTPException) as exc_info:
        await limiter(request)

    assert exc_info.value.status_code == 429
    assert "Retry-After" in exc_info.value.headers


@pytest.mark.asyncio
async def test_rate_limiter_keys_by_ip():
    """Different IPs have independent counters."""
    from unittest.mock import MagicMock

    limiter = RateLimiter("test-ip", max_requests=1, window_seconds=3600)

    req1 = MagicMock()
    req1.client.host = "1.2.3.4"
    await limiter(req1)  # IP 1 uses its one request

    req2 = MagicMock()
    req2.client.host = "5.6.7.8"
    await limiter(req2)  # IP 2 should still succeed
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend
uv run pytest tests/test_auth_rate_limits_wave5c.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.auth.rate_limit'`

- [ ] **Step 3: Implement RateLimiter**

Create `backend/app/auth/rate_limit.py`:

```python
"""Per-endpoint rate limiting via FastAPI Depends().

Uses cache.incr() with TTL for counting. Redis provides fixed-window
semantics (TTL set on first increment). The in-memory fallback provides
sliding-window semantics (TTL resets on each increment). Tests verify
count-and-reject logic; exact window semantics require Redis.
"""

from fastapi import HTTPException, Request, status

from app.core.cache import cache


class RateLimiter:
    """FastAPI dependency for per-endpoint rate limiting.

    Usage:
        @router.post("/reset", dependencies=[Depends(RateLimiter("reset", 3, 3600))])
        async def request_reset(...): ...

    Or as a parameter dependency:
        async def request_reset(
            _rate_limit: None = Depends(RateLimiter("reset", 3, 3600)),
        ): ...
    """

    def __init__(self, key_prefix: str, max_requests: int, window_seconds: int):
        """Initialize rate limiter.

        Args:
            key_prefix: Namespace prefix for cache keys (e.g., "reset-request")
            max_requests: Maximum requests allowed within window
            window_seconds: Window duration in seconds
        """
        self.key_prefix = key_prefix
        self.max_requests = max_requests
        self.window_seconds = window_seconds

    async def __call__(self, request: Request) -> None:
        """Check rate limit; raise 429 if exceeded.

        Args:
            request: FastAPI request (used to extract client IP)

        Raises:
            HTTPException: 429 with Retry-After header if limit exceeded
        """
        client_ip = request.client.host if request.client else "unknown"
        key = f"rate:{self.key_prefix}:{client_ip}"
        count = await cache.incr(key, ttl=self.window_seconds)

        if count > self.max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Max {self.max_requests} requests per {self.window_seconds}s.",
                headers={"Retry-After": str(self.window_seconds)},
            )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend
uv run pytest tests/test_auth_rate_limits_wave5c.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Run full backend suite**

```bash
cd backend
make test
```

Expected: ~1097 passing.

- [ ] **Step 6: Commit**

```bash
git add backend/app/auth/rate_limit.py backend/tests/test_auth_rate_limits_wave5c.py
git commit -m "feat(auth): add per-endpoint RateLimiter dependency"
```

---

## Task 5: Credential token repository

**Commit message:** `feat(auth): add credential token repository with create/consume/invalidate`

**Files:**
- Create: `backend/app/auth/credential_tokens.py`
- Create: `backend/tests/test_credential_tokens.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_credential_tokens.py`:

```python
"""Tests for credential token repository."""

from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio

from app.auth.credential_tokens import CredentialTokenService


@pytest_asyncio.fixture
async def token_service(db_session):
    """Create a CredentialTokenService with test session."""
    return CredentialTokenService(db_session)


@pytest.mark.asyncio
async def test_create_token_returns_raw_token(token_service):
    """create_token returns the raw URL-safe token (not the hash)."""
    raw_token, db_token = await token_service.create_token(
        purpose="invite",
        email="test@example.com",
        metadata={"role": "curator"},
    )
    assert len(raw_token) > 30  # secrets.token_urlsafe(32) is ~43 chars
    assert db_token.token_sha256 != raw_token  # stored hash != raw
    assert db_token.purpose == "invite"
    assert db_token.email == "test@example.com"
    assert db_token.metadata_ == {"role": "curator"}
    assert db_token.used_at is None


@pytest.mark.asyncio
async def test_create_token_with_user_id(token_service, db_session):
    """create_token can bind to an existing user."""
    from app.auth.password import get_password_hash
    from app.models.user import User

    user = User(
        username="verifyuser",
        email="verify@example.com",
        hashed_password=get_password_hash("TestPass!2026"),
        role="viewer",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    raw_token, db_token = await token_service.create_token(
        purpose="verify",
        email="verify@example.com",
        user_id=user.id,
    )
    assert db_token.user_id == user.id


@pytest.mark.asyncio
async def test_verify_and_consume_valid_token(token_service):
    """verify_and_consume succeeds for valid, unused, unexpired token."""
    raw_token, _ = await token_service.create_token(
        purpose="reset",
        email="reset@example.com",
    )
    consumed = await token_service.verify_and_consume(raw_token, purpose="reset")
    assert consumed is not None
    assert consumed.email == "reset@example.com"
    assert consumed.used_at is not None


@pytest.mark.asyncio
async def test_verify_and_consume_rejects_wrong_purpose(token_service):
    """verify_and_consume returns None if purpose doesn't match."""
    raw_token, _ = await token_service.create_token(
        purpose="invite",
        email="test@example.com",
    )
    result = await token_service.verify_and_consume(raw_token, purpose="reset")
    assert result is None


@pytest.mark.asyncio
async def test_verify_and_consume_rejects_already_used(token_service):
    """verify_and_consume returns None for already-consumed tokens."""
    raw_token, _ = await token_service.create_token(
        purpose="reset",
        email="test@example.com",
    )
    # Consume once
    await token_service.verify_and_consume(raw_token, purpose="reset")
    # Second attempt fails
    result = await token_service.verify_and_consume(raw_token, purpose="reset")
    assert result is None


@pytest.mark.asyncio
async def test_verify_and_consume_rejects_expired(token_service):
    """verify_and_consume returns None for expired tokens."""
    raw_token, _ = await token_service.create_token(
        purpose="reset",
        email="test@example.com",
        expires_in=timedelta(seconds=-1),  # already expired
    )
    result = await token_service.verify_and_consume(raw_token, purpose="reset")
    assert result is None


@pytest.mark.asyncio
async def test_invalidate_by_email_and_purpose(token_service):
    """invalidate_by_email_and_purpose marks existing tokens as used."""
    raw1, _ = await token_service.create_token(
        purpose="reset", email="test@example.com"
    )
    raw2, _ = await token_service.create_token(
        purpose="reset", email="test@example.com"
    )

    count = await token_service.invalidate_by_email_and_purpose(
        email="test@example.com", purpose="reset"
    )
    assert count == 2

    # Both tokens should now be unusable
    assert await token_service.verify_and_consume(raw1, purpose="reset") is None
    assert await token_service.verify_and_consume(raw2, purpose="reset") is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend
uv run pytest tests/test_credential_tokens.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.auth.credential_tokens'`

- [ ] **Step 3: Implement CredentialTokenService**

Create `backend/app/auth/credential_tokens.py`:

```python
"""Credential token service for identity lifecycle flows.

Handles creation, verification, consumption, and invalidation of
single-use tokens for invite, password reset, and email verification.
"""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.credential_token import CredentialToken

# Default token expiry: 24 hours
DEFAULT_EXPIRY = timedelta(hours=24)


def _hash_token(raw_token: str) -> str:
    """Compute SHA-256 hex hash of a raw token."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


class CredentialTokenService:
    """Service for credential token CRUD operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_token(
        self,
        *,
        purpose: str,
        email: str,
        user_id: int | None = None,
        metadata: dict | None = None,
        expires_in: timedelta = DEFAULT_EXPIRY,
    ) -> tuple[str, CredentialToken]:
        """Create a new credential token.

        Args:
            purpose: Token purpose ('invite', 'reset', 'verify')
            email: Email address to bind
            user_id: Optional FK to users.id (NULL for invites)
            metadata: Optional purpose-specific data
            expires_in: Time until expiry (default 24h)

        Returns:
            Tuple of (raw_token, db_token). The raw_token is the URL-safe
            string to send to the user. The db_token is the persisted row
            with the SHA-256 hash.
        """
        raw_token = secrets.token_urlsafe(32)
        token_hash = _hash_token(raw_token)
        now = datetime.now(timezone.utc)

        db_token = CredentialToken(
            user_id=user_id,
            purpose=purpose,
            token_sha256=token_hash,
            email=email,
            expires_at=now + expires_in,
            metadata_=metadata,
        )
        self.db.add(db_token)
        await self.db.commit()
        await self.db.refresh(db_token)

        return raw_token, db_token

    async def verify_and_consume(
        self, raw_token: str, *, purpose: str
    ) -> CredentialToken | None:
        """Verify a token and mark it as consumed in one atomic step.

        Args:
            raw_token: The raw URL-safe token from the user
            purpose: Expected purpose ('invite', 'reset', 'verify')

        Returns:
            The consumed CredentialToken row, or None if invalid/expired/used.
        """
        token_hash = _hash_token(raw_token)
        now = datetime.now(timezone.utc)

        # Look up by hash
        result = await self.db.execute(
            select(CredentialToken).where(
                CredentialToken.token_sha256 == token_hash,
                CredentialToken.purpose == purpose,
            )
        )
        db_token = result.scalar_one_or_none()

        if db_token is None:
            return None

        # Constant-time comparison for defense in depth (see spec §11 R1)
        if not hmac.compare_digest(db_token.token_sha256, token_hash):
            return None

        # Check not already used
        if db_token.used_at is not None:
            return None

        # Check not expired
        if db_token.expires_at <= now:
            return None

        # Consume atomically
        db_token.used_at = now
        await self.db.commit()
        await self.db.refresh(db_token)

        return db_token

    async def invalidate_by_email_and_purpose(
        self, *, email: str, purpose: str
    ) -> int:
        """Mark all unused tokens for an email+purpose as consumed.

        Used when creating a new token (invalidates prior ones) or
        when a password is changed (invalidates all reset tokens).

        Returns:
            Number of tokens invalidated.
        """
        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            update(CredentialToken)
            .where(
                CredentialToken.email == email,
                CredentialToken.purpose == purpose,
                CredentialToken.used_at.is_(None),
            )
            .values(used_at=now)
        )
        await self.db.commit()
        return result.rowcount
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend
uv run pytest tests/test_credential_tokens.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Run full backend suite**

```bash
cd backend
make test
```

Expected: ~1104 passing.

- [ ] **Step 6: Commit**

```bash
git add backend/app/auth/credential_tokens.py backend/tests/test_credential_tokens.py
git commit -m "feat(auth): add credential token repository with create/consume/invalidate"
```

---

## Task 6: Invite endpoints

**Commit message:** `feat(api): add POST /auth/users/invite and POST /auth/invite/accept/{token}`

**Files:**
- Modify: `backend/app/schemas/auth.py` (add invite schemas)
- Modify: `backend/app/api/auth_endpoints.py` (add 2 endpoints)
- Create: `backend/tests/test_auth_invite.py`

- [ ] **Step 1: Add invite schemas**

Add to `backend/app/schemas/auth.py`:

```python
class InviteRequest(BaseModel):
    """Admin invite request."""

    email: EmailStr
    role: str = Field("viewer", pattern="^(admin|curator|viewer)$")


class InviteResponse(BaseModel):
    """Invite creation response."""

    email: str
    role: str
    expires_at: datetime
    token: str | None = None  # Dev-only: raw token for testing


class InviteAcceptRequest(BaseModel):
    """Invite accept request — user sets their own credentials."""

    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8)
    full_name: str | None = Field(None, max_length=255)

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        """Validate username format (same rules as UserCreate)."""
        v = v.lower()
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Username can only contain letters, numbers, - and _")
        if v in ["admin", "root", "system", "administrator"]:
            raise ValueError(f"Username '{v}' is reserved")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password strength."""
        validate_password_strength(v)
        return v
```

- [ ] **Step 2: Write the failing tests**

Create `backend/tests/test_auth_invite.py`:

```python
"""Tests for invite endpoints."""

import logging

import pytest


@pytest.mark.asyncio
async def test_admin_can_create_invite(async_client, admin_headers):
    """POST /auth/users/invite creates an invite token."""
    resp = await async_client.post(
        "/api/v2/auth/users/invite",
        json={"email": "newcurator@example.com", "role": "curator"},
        headers=admin_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "newcurator@example.com"
    assert data["role"] == "curator"
    assert "expires_at" in data
    # Dev mode should include the raw token
    assert "token" in data


@pytest.mark.asyncio
async def test_invite_accept_creates_user(async_client, admin_headers):
    """POST /auth/invite/accept/{token} creates a user."""
    # Create invite
    invite_resp = await async_client.post(
        "/api/v2/auth/users/invite",
        json={"email": "accept@example.com", "role": "curator"},
        headers=admin_headers,
    )
    assert invite_resp.status_code == 201
    token = invite_resp.json()["token"]

    # Accept invite
    accept_resp = await async_client.post(
        f"/api/v2/auth/invite/accept/{token}",
        json={
            "username": "accepted-user",
            "password": "SecurePass!2026",
            "full_name": "Accepted User",
        },
    )
    assert accept_resp.status_code == 201
    user = accept_resp.json()
    assert user["email"] == "accept@example.com"
    assert user["username"] == "accepted-user"
    assert user["role"] == "curator"
    assert user["is_verified"] is True


@pytest.mark.asyncio
async def test_invite_accept_rejects_duplicate_username(async_client, admin_headers):
    """Invite accept with existing username returns 409."""
    # Create two invites
    invite1 = await async_client.post(
        "/api/v2/auth/users/invite",
        json={"email": "user1@example.com", "role": "viewer"},
        headers=admin_headers,
    )
    invite2 = await async_client.post(
        "/api/v2/auth/users/invite",
        json={"email": "user2@example.com", "role": "viewer"},
        headers=admin_headers,
    )

    # Accept first invite
    await async_client.post(
        f"/api/v2/auth/invite/accept/{invite1.json()['token']}",
        json={"username": "samename", "password": "SecurePass!2026", "full_name": "User 1"},
    )

    # Accept second invite with same username
    resp = await async_client.post(
        f"/api/v2/auth/invite/accept/{invite2.json()['token']}",
        json={"username": "samename", "password": "SecurePass!2026", "full_name": "User 2"},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_invite_accept_rejects_expired_token(async_client, admin_headers, db_session):
    """Expired invite token is rejected."""
    from datetime import datetime, timedelta, timezone
    from app.auth.credential_tokens import CredentialTokenService

    svc = CredentialTokenService(db_session)
    raw_token, _ = await svc.create_token(
        purpose="invite",
        email="expired@example.com",
        metadata={"role": "viewer"},
        expires_in=timedelta(seconds=-1),
    )

    resp = await async_client.post(
        f"/api/v2/auth/invite/accept/{raw_token}",
        json={"username": "expireduser", "password": "SecurePass!2026", "full_name": "Expired"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_invite_accept_rejects_already_used_token(async_client, admin_headers):
    """Already-used invite token is rejected on second use."""
    invite_resp = await async_client.post(
        "/api/v2/auth/users/invite",
        json={"email": "once@example.com", "role": "viewer"},
        headers=admin_headers,
    )
    token = invite_resp.json()["token"]

    # Use once
    await async_client.post(
        f"/api/v2/auth/invite/accept/{token}",
        json={"username": "firstuse", "password": "SecurePass!2026", "full_name": "First"},
    )

    # Use again
    resp = await async_client.post(
        f"/api/v2/auth/invite/accept/{token}",
        json={"username": "seconduse", "password": "SecurePass!2026", "full_name": "Second"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_reinvite_invalidates_old_token(async_client, admin_headers):
    """Re-inviting the same email invalidates the old token."""
    # First invite
    invite1 = await async_client.post(
        "/api/v2/auth/users/invite",
        json={"email": "reinvite@example.com", "role": "viewer"},
        headers=admin_headers,
    )
    token1 = invite1.json()["token"]

    # Second invite (same email)
    invite2 = await async_client.post(
        "/api/v2/auth/users/invite",
        json={"email": "reinvite@example.com", "role": "curator"},
        headers=admin_headers,
    )
    token2 = invite2.json()["token"]

    # Old token should be invalid
    resp1 = await async_client.post(
        f"/api/v2/auth/invite/accept/{token1}",
        json={"username": "oldtoken", "password": "SecurePass!2026", "full_name": "Old"},
    )
    assert resp1.status_code == 400

    # New token should work
    resp2 = await async_client.post(
        f"/api/v2/auth/invite/accept/{token2}",
        json={"username": "newtoken", "password": "SecurePass!2026", "full_name": "New"},
    )
    assert resp2.status_code == 201
    assert resp2.json()["role"] == "curator"


@pytest.mark.asyncio
async def test_invite_logs_via_console_sender(async_client, admin_headers, caplog):
    """ConsoleEmailSender logs the invite email."""
    with caplog.at_level(logging.INFO, logger="app.auth.email"):
        await async_client.post(
            "/api/v2/auth/users/invite",
            json={"email": "logged@example.com", "role": "viewer"},
            headers=admin_headers,
        )
    assert "logged@example.com" in caplog.text


@pytest.mark.asyncio
async def test_non_admin_cannot_invite(async_client, viewer_headers):
    """Non-admin user gets 403 on invite endpoint."""
    resp = await async_client.post(
        "/api/v2/auth/users/invite",
        json={"email": "hacker@example.com", "role": "admin"},
        headers=viewer_headers,
    )
    assert resp.status_code == 403
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
cd backend
uv run pytest tests/test_auth_invite.py -v
```

Expected: FAIL — endpoints don't exist yet.

- [ ] **Step 4: Implement invite endpoints**

Add to `backend/app/api/auth_endpoints.py`:

Import additions at top of file:

```python
from app.auth.credential_tokens import CredentialTokenService
from app.auth.email import get_email_sender
from app.auth.rate_limit import RateLimiter
from app.schemas.auth import (
    # ... existing imports ...
    InviteAcceptRequest,
    InviteRequest,
    InviteResponse,
)
```

Add to `users_router` (admin-only, `/users` prefix):

```python
@users_router.post("/invite", response_model=InviteResponse, status_code=status.HTTP_201_CREATED)
async def create_invite(
    invite_data: InviteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InviteResponse:
    """Invite a new user by email (admin only).

    Creates a credential token bound to the target email. The invited
    user receives a link to accept the invite and set their credentials.
    Re-inviting the same email invalidates prior invite tokens.
    """
    token_svc = CredentialTokenService(db)

    # Invalidate any existing invite tokens for this email
    await token_svc.invalidate_by_email_and_purpose(
        email=invite_data.email, purpose="invite"
    )

    raw_token, db_token = await token_svc.create_token(
        purpose="invite",
        email=invite_data.email,
        metadata={"role": invite_data.role},
    )

    # Dispatch invite email
    sender = get_email_sender()
    accept_url = f"{settings.CORS_ORIGINS.split(',')[0]}/accept-invite/{raw_token}?email={invite_data.email}"
    await sender.send(
        to=invite_data.email,
        subject=f"You've been invited to {settings.email.from_name}",
        body_html=f"<p>You've been invited as a {invite_data.role}. "
        f"Click here to accept: {accept_url}</p>",
    )

    await log_user_action(
        db=db,
        user_id=current_user.id,
        action="USER_INVITED",
        details=f"Admin '{current_user.username}' invited '{invite_data.email}' as {invite_data.role}",
    )

    response = InviteResponse(
        email=invite_data.email,
        role=invite_data.role,
        expires_at=db_token.expires_at,
    )

    # Dev-only: include raw token for testing
    if settings.environment != "production":
        response.token = raw_token

    return response
```

Add to main `router` (anonymous):

```python
@router.post(
    "/invite/accept/{token}",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RateLimiter("invite-accept", 5, 3600))],
)
async def accept_invite(
    token: str,
    accept_data: InviteAcceptRequest,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Accept an invite and create a user account.

    The token must be valid, unused, and unexpired with purpose='invite'.
    The user is created with is_verified=True (email ownership proved
    by receiving the invite).
    """
    token_svc = CredentialTokenService(db)
    db_token = await token_svc.verify_and_consume(token, purpose="invite")

    if db_token is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid, expired, or already-used invite token.",
        )

    repo = UserRepository(db)

    # Check username uniqueness
    if await repo.get_by_username(accept_data.username):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Username '{accept_data.username}' already exists",
        )

    # Check email uniqueness (in case admin created the user separately)
    if await repo.get_by_email(db_token.email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Email '{db_token.email}' already exists",
        )

    # Extract role from token metadata
    role = (db_token.metadata_ or {}).get("role", "viewer")

    # Create user
    user = User(
        username=accept_data.username,
        email=db_token.email,
        hashed_password=get_password_hash(accept_data.password),
        full_name=accept_data.full_name,
        role=role,
        is_active=True,
        is_verified=True,  # Proved email ownership by using invite
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    await log_user_action(
        db=db,
        user_id=user.id,
        action="INVITE_ACCEPTED",
        details=f"User '{user.username}' accepted invite for '{db_token.email}'",
    )

    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        permissions=user.get_permissions(),
        is_active=user.is_active,
        is_verified=user.is_verified,
        last_login=user.last_login,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )
```

Also add the import for `UserRepository` if not already present at top of file:

```python
from app.repositories.user_repository import UserRepository
```

And the import for `get_password_hash`:

```python
from app.auth.password import get_password_hash
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd backend
uv run pytest tests/test_auth_invite.py -v
```

Expected: 8 passed.

- [ ] **Step 6: Run full backend suite + lint**

```bash
cd backend
make check
```

Expected: All checks pass.

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/auth.py backend/app/api/auth_endpoints.py backend/tests/test_auth_invite.py
git commit -m "feat(api): add POST /auth/users/invite and POST /auth/invite/accept/{token}"
```

---

## Task 7: Password reset endpoints

**Commit message:** `feat(api): add password reset request and confirm endpoints`

**Files:**
- Modify: `backend/app/schemas/auth.py` (add reset schemas)
- Modify: `backend/app/api/auth_endpoints.py` (add 2 endpoints)
- Create: `backend/tests/test_auth_password_reset.py`

- [ ] **Step 1: Add password reset schemas**

Add to `backend/app/schemas/auth.py`:

```python
class PasswordResetRequest(BaseModel):
    """Password reset request — email only."""

    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Password reset confirmation — new password."""

    new_password: str = Field(..., min_length=8)

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        """Validate password strength."""
        validate_password_strength(v)
        return v


class MessageResponse(BaseModel):
    """Generic message response."""

    message: str
    token: str | None = None  # Dev-only: raw token for testing
```

- [ ] **Step 2: Write the failing tests**

Create `backend/tests/test_auth_password_reset.py`:

```python
"""Tests for password reset endpoints."""

import pytest


@pytest.mark.asyncio
async def test_reset_request_returns_202_for_existing_email(
    async_client, admin_headers, db_session
):
    """POST /auth/password-reset/request returns 202 when email exists."""
    # Admin user exists from fixture
    me_resp = await async_client.get("/api/v2/auth/me", headers=admin_headers)
    admin_email = me_resp.json()["email"]

    resp = await async_client.post(
        "/api/v2/auth/password-reset/request",
        json={"email": admin_email},
    )
    assert resp.status_code == 202


@pytest.mark.asyncio
async def test_reset_request_returns_202_for_nonexistent_email(async_client):
    """POST /auth/password-reset/request returns 202 even when email doesn't exist."""
    resp = await async_client.post(
        "/api/v2/auth/password-reset/request",
        json={"email": "nonexistent@example.com"},
    )
    assert resp.status_code == 202


@pytest.mark.asyncio
async def test_reset_confirm_changes_password(async_client, admin_headers, db_session):
    """Full reset flow: request → get token → confirm → login with new password."""
    me_resp = await async_client.get("/api/v2/auth/me", headers=admin_headers)
    admin_email = me_resp.json()["email"]
    admin_username = me_resp.json()["username"]

    # Request reset
    reset_resp = await async_client.post(
        "/api/v2/auth/password-reset/request",
        json={"email": admin_email},
    )
    assert reset_resp.status_code == 202
    token = reset_resp.json().get("token")
    assert token is not None  # Dev mode includes token

    # Confirm reset
    confirm_resp = await async_client.post(
        f"/api/v2/auth/password-reset/confirm/{token}",
        json={"new_password": "NewSecurePass!2026"},
    )
    assert confirm_resp.status_code == 200

    # Login with new password
    login_resp = await async_client.post(
        "/api/v2/auth/login",
        json={"username": admin_username, "password": "NewSecurePass!2026"},
    )
    assert login_resp.status_code == 200


@pytest.mark.asyncio
async def test_reset_confirm_rejects_invalid_token(async_client):
    """Invalid token returns 400."""
    resp = await async_client.post(
        "/api/v2/auth/password-reset/confirm/invalid-token-xyz",
        json={"new_password": "NewSecurePass!2026"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_reset_confirm_invalidates_old_tokens(async_client, admin_headers):
    """After successful reset, prior tokens for same email are invalidated."""
    me_resp = await async_client.get("/api/v2/auth/me", headers=admin_headers)
    admin_email = me_resp.json()["email"]

    # Create two reset tokens
    resp1 = await async_client.post(
        "/api/v2/auth/password-reset/request",
        json={"email": admin_email},
    )
    token1 = resp1.json()["token"]

    resp2 = await async_client.post(
        "/api/v2/auth/password-reset/request",
        json={"email": admin_email},
    )
    token2 = resp2.json()["token"]

    # Use token2
    await async_client.post(
        f"/api/v2/auth/password-reset/confirm/{token2}",
        json={"new_password": "NewSecurePass!2026"},
    )

    # token1 should be invalid
    resp = await async_client.post(
        f"/api/v2/auth/password-reset/confirm/{token1}",
        json={"new_password": "AnotherPass!2026"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_reset_confirm_rejects_already_used_token(async_client, admin_headers):
    """Token can only be used once."""
    me_resp = await async_client.get("/api/v2/auth/me", headers=admin_headers)
    admin_email = me_resp.json()["email"]

    resp = await async_client.post(
        "/api/v2/auth/password-reset/request",
        json={"email": admin_email},
    )
    token = resp.json()["token"]

    # Use once
    await async_client.post(
        f"/api/v2/auth/password-reset/confirm/{token}",
        json={"new_password": "NewSecurePass!2026"},
    )

    # Use again
    resp2 = await async_client.post(
        f"/api/v2/auth/password-reset/confirm/{token}",
        json={"new_password": "AnotherPass!2026"},
    )
    assert resp2.status_code == 400
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
cd backend
uv run pytest tests/test_auth_password_reset.py -v
```

Expected: FAIL — endpoints don't exist yet.

- [ ] **Step 4: Implement password reset endpoints**

Add imports to `backend/app/api/auth_endpoints.py`:

```python
from app.schemas.auth import (
    # ... existing + invite imports ...
    MessageResponse,
    PasswordResetConfirm,
    PasswordResetRequest,
)
```

Add to main `router` (anonymous):

```python
@router.post(
    "/password-reset/request",
    response_model=MessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(RateLimiter("reset-request", 3, 3600))],
)
async def request_password_reset(
    reset_data: PasswordResetRequest,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Request a password reset email.

    Always returns 202 regardless of whether the email exists —
    constant-time anti-enumeration per OWASP Forgot Password Cheat Sheet.
    """
    repo = UserRepository(db)
    user = await repo.get_by_email(reset_data.email)

    raw_token = None
    if user:
        token_svc = CredentialTokenService(db)

        # Invalidate prior reset tokens for this email
        await token_svc.invalidate_by_email_and_purpose(
            email=reset_data.email, purpose="reset"
        )

        raw_token, _ = await token_svc.create_token(
            purpose="reset",
            email=reset_data.email,
            user_id=user.id,
        )

        sender = get_email_sender()
        reset_url = f"{settings.CORS_ORIGINS.split(',')[0]}/reset-password/{raw_token}"
        await sender.send(
            to=reset_data.email,
            subject=f"Password Reset - {settings.email.from_name}",
            body_html=f"<p>Reset your password: {reset_url}</p>",
        )

    response = MessageResponse(
        message="If an account exists with that email, a reset link has been sent."
    )

    # Dev-only: include raw token for testing
    if settings.environment != "production" and raw_token:
        response.token = raw_token

    return response


@router.post(
    "/password-reset/confirm/{token}",
    response_model=MessageResponse,
    dependencies=[Depends(RateLimiter("reset-confirm", 5, 3600))],
)
async def confirm_password_reset(
    token: str,
    reset_data: PasswordResetConfirm,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Confirm a password reset with a valid token."""
    token_svc = CredentialTokenService(db)
    db_token = await token_svc.verify_and_consume(token, purpose="reset")

    if db_token is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid, expired, or already-used reset token.",
        )

    repo = UserRepository(db)
    user = await repo.get_by_id(db_token.user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User associated with this token no longer exists.",
        )

    # Update password
    user.hashed_password = get_password_hash(reset_data.new_password)
    await db.commit()

    # Invalidate all remaining reset tokens for this email
    await token_svc.invalidate_by_email_and_purpose(
        email=db_token.email, purpose="reset"
    )

    await log_user_action(
        db=db,
        user_id=user.id,
        action="PASSWORD_RESET",
        details=f"User '{user.username}' reset password via token",
    )

    return MessageResponse(message="Password reset successful.")
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd backend
uv run pytest tests/test_auth_password_reset.py -v
```

Expected: 6 passed.

- [ ] **Step 6: Run full backend suite + lint**

```bash
cd backend
make check
```

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/auth.py backend/app/api/auth_endpoints.py backend/tests/test_auth_password_reset.py
git commit -m "feat(api): add password reset request and confirm endpoints"
```

---

## Task 8: Verify email endpoints + auto-dispatch on admin create

**Commit message:** `feat(api): add verify-email consume and resend endpoints + auto-dispatch on user create`

**Files:**
- Modify: `backend/app/api/auth_endpoints.py` (add 2 endpoints, modify create_user)
- Create: `backend/tests/test_auth_email_verify.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_auth_email_verify.py`:

```python
"""Tests for email verification endpoints."""

import logging

import pytest


@pytest.mark.asyncio
async def test_admin_create_user_dispatches_verify_email(
    async_client, admin_headers, caplog
):
    """POST /auth/users (admin create) auto-dispatches verification email."""
    with caplog.at_level(logging.INFO, logger="app.auth.email"):
        resp = await async_client.post(
            "/api/v2/auth/users",
            json={
                "username": "verifytest",
                "email": "verifytest@example.com",
                "password": "VerifyTest!2026",
                "full_name": "Verify Test",
                "role": "viewer",
            },
            headers=admin_headers,
        )
    assert resp.status_code == 201
    assert resp.json()["is_verified"] is False
    assert "verifytest@example.com" in caplog.text


@pytest.mark.asyncio
async def test_verify_email_sets_verified(async_client, admin_headers, db_session):
    """POST /auth/verify-email/{token} sets is_verified=True."""
    # Create user (triggers verify email with dev token)
    create_resp = await async_client.post(
        "/api/v2/auth/users",
        json={
            "username": "verifyable",
            "email": "verifyable@example.com",
            "password": "VerifyMe!2026",
            "full_name": "Verifyable User",
            "role": "viewer",
        },
        headers=admin_headers,
    )
    assert create_resp.status_code == 201
    user_id = create_resp.json()["id"]

    # Get the verify token from credential_tokens table
    from app.models.credential_token import CredentialToken
    from sqlalchemy import select

    result = await db_session.execute(
        select(CredentialToken).where(
            CredentialToken.email == "verifyable@example.com",
            CredentialToken.purpose == "verify",
        )
    )
    # We need the raw token, which isn't stored. In dev mode the create_user
    # response should include it. Let's check.
    # Actually, the verify token is dispatched via email, not returned in
    # create_user response. We need to use the token service to create one
    # for testing, or check the response.
    # For now, create a token directly:
    from app.auth.credential_tokens import CredentialTokenService

    svc = CredentialTokenService(db_session)
    raw_token, _ = await svc.create_token(
        purpose="verify",
        email="verifyable@example.com",
        user_id=user_id,
    )

    # Verify email
    resp = await async_client.post(f"/api/v2/auth/verify-email/{raw_token}")
    assert resp.status_code == 200

    # Check user is now verified
    user_resp = await async_client.get(
        f"/api/v2/auth/users/{user_id}",
        headers=admin_headers,
    )
    assert user_resp.json()["is_verified"] is True


@pytest.mark.asyncio
async def test_verify_email_rejects_invalid_token(async_client):
    """Invalid verify token returns 400."""
    resp = await async_client.post("/api/v2/auth/verify-email/invalid-token-xyz")
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_verify_email_single_use(async_client, db_session):
    """Verify token can only be used once."""
    from app.auth.credential_tokens import CredentialTokenService
    from app.auth.password import get_password_hash
    from app.models.user import User

    # Create a user
    user = User(
        username="singleuse",
        email="singleuse@example.com",
        hashed_password=get_password_hash("TestPass!2026"),
        role="viewer",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    svc = CredentialTokenService(db_session)
    raw_token, _ = await svc.create_token(
        purpose="verify", email="singleuse@example.com", user_id=user.id
    )

    # Use once — should succeed
    resp1 = await async_client.post(f"/api/v2/auth/verify-email/{raw_token}")
    assert resp1.status_code == 200

    # Use again — should fail
    resp2 = await async_client.post(f"/api/v2/auth/verify-email/{raw_token}")
    assert resp2.status_code == 400


@pytest.mark.asyncio
async def test_verify_resend_creates_new_token(async_client, db_session):
    """POST /auth/verify-email/resend creates a new verify token."""
    from app.auth.password import get_password_hash
    from app.models.user import User
    from app.auth.tokens import create_access_token

    # Create unverified user
    user = User(
        username="resenduser",
        email="resend@example.com",
        hashed_password=get_password_hash("TestPass!2026"),
        role="viewer",
        is_active=True,
        is_verified=False,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Get auth token for this user
    access_token = create_access_token(
        user.username, user.role, user.get_permissions()
    )
    headers = {"Authorization": f"Bearer {access_token}"}

    resp = await async_client.post(
        "/api/v2/auth/verify-email/resend",
        headers=headers,
    )
    assert resp.status_code == 202


@pytest.mark.asyncio
async def test_verify_resend_rejects_already_verified(async_client, admin_headers):
    """Resend returns 400 if user is already verified."""
    # Admin user is already verified
    resp = await async_client.post(
        "/api/v2/auth/verify-email/resend",
        headers=admin_headers,
    )
    assert resp.status_code == 400
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend
uv run pytest tests/test_auth_email_verify.py -v
```

Expected: FAIL — endpoints don't exist yet.

- [ ] **Step 3: Implement verify endpoints and modify create_user**

Add to main `router` in `backend/app/api/auth_endpoints.py`:

```python
@router.post(
    "/verify-email/{token}",
    response_model=MessageResponse,
    dependencies=[Depends(RateLimiter("verify-email", 5, 3600))],
)
async def verify_email(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Verify email address using a credential token."""
    token_svc = CredentialTokenService(db)
    db_token = await token_svc.verify_and_consume(token, purpose="verify")

    if db_token is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid, expired, or already-used verification token.",
        )

    repo = UserRepository(db)
    user = await repo.get_by_id(db_token.user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User associated with this token no longer exists.",
        )

    user.is_verified = True
    await db.commit()

    await log_user_action(
        db=db,
        user_id=user.id,
        action="EMAIL_VERIFIED",
        details=f"User '{user.username}' verified email '{db_token.email}'",
    )

    return MessageResponse(message="Email verified successfully.")


@router.post(
    "/verify-email/resend",
    response_model=MessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(RateLimiter("verify-resend", 3, 3600))],
)
async def resend_verification(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Resend email verification (authenticated, unverified users only)."""
    if current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is already verified.",
        )

    token_svc = CredentialTokenService(db)

    # Invalidate prior verify tokens
    await token_svc.invalidate_by_email_and_purpose(
        email=current_user.email, purpose="verify"
    )

    raw_token, _ = await token_svc.create_token(
        purpose="verify",
        email=current_user.email,
        user_id=current_user.id,
    )

    sender = get_email_sender()
    verify_url = f"{settings.CORS_ORIGINS.split(',')[0]}/verify-email/{raw_token}"
    await sender.send(
        to=current_user.email,
        subject=f"Verify your email - {settings.email.from_name}",
        body_html=f"<p>Verify your email: {verify_url}</p>",
    )

    response = MessageResponse(message="Verification email sent.")
    if settings.environment != "production":
        response.token = raw_token

    return response
```

**IMPORTANT:** The `resend` route must be registered BEFORE the `/{token}` route, otherwise FastAPI will treat "resend" as a token value. Ensure the route order in the file is:
1. `POST /verify-email/resend` (specific path)
2. `POST /verify-email/{token}` (parameterized path)

**Modify `create_user` endpoint** to auto-dispatch verification email:

In the existing `create_user` function in `users_router`, add after the user is created and the audit log is written, before the return statement:

```python
    # Auto-dispatch email verification
    token_svc = CredentialTokenService(db)
    raw_token, _ = await token_svc.create_token(
        purpose="verify",
        email=user.email,
        user_id=user.id,
    )

    sender = get_email_sender()
    verify_url = f"{settings.CORS_ORIGINS.split(',')[0]}/verify-email/{raw_token}"
    await sender.send(
        to=user.email,
        subject=f"Verify your email - {settings.email.from_name}",
        body_html=f"<p>Verify your email: {verify_url}</p>",
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend
uv run pytest tests/test_auth_email_verify.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Run full backend suite + lint**

```bash
cd backend
make check
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/auth_endpoints.py backend/tests/test_auth_email_verify.py
git commit -m "feat(api): add verify-email consume and resend endpoints + auto-dispatch on user create"
```

---

## Task 9: Invite-only negative test

**Commit message:** `test(auth): verify POST /auth/register does not exist (invite-only)`

**Files:**
- Create: `backend/tests/test_register_endpoint_absent.py`

- [ ] **Step 1: Write the test**

Create `backend/tests/test_register_endpoint_absent.py`:

```python
"""Negative test: self-registration endpoint must not exist.

HNF1B-DB is invite-only. POST /api/v2/auth/register must return
404 (no route) or 405 (method not allowed). If this test fails,
someone added a registration endpoint — that is a policy violation.
"""

import pytest


@pytest.mark.asyncio
async def test_register_endpoint_absent(async_client):
    """POST /api/v2/auth/register returns 404 or 405."""
    resp = await async_client.post(
        "/api/v2/auth/register",
        json={
            "username": "hacker",
            "email": "hacker@example.com",
            "password": "H4ck3rP4ss!",
        },
    )
    assert resp.status_code in (404, 405), (
        f"Expected 404 or 405 but got {resp.status_code}. "
        "A registration endpoint exists — HNF1B-DB is invite-only."
    )
```

- [ ] **Step 2: Run the test**

```bash
cd backend
uv run pytest tests/test_register_endpoint_absent.py -v
```

Expected: PASS (the endpoint doesn't exist).

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_register_endpoint_absent.py
git commit -m "test(auth): verify POST /auth/register does not exist (invite-only)"
```

---

## Task 10: Frontend — ForgotPassword + ResetPassword views

**Commit message:** `feat(frontend): add ForgotPassword and ResetPassword views`

**Files:**
- Create: `frontend/src/views/ForgotPassword.vue`
- Create: `frontend/src/views/ResetPassword.vue`
- Modify: `frontend/src/api/domain/auth.js`
- Modify: `frontend/src/router/index.js`
- Modify: `frontend/src/views/Login.vue`
- Create: `frontend/tests/unit/views/ForgotPassword.spec.js`
- Create: `frontend/tests/unit/views/ResetPassword.spec.js`

- [ ] **Step 1: Add API functions**

Add to `frontend/src/api/domain/auth.js`:

```javascript
/**
 * Request a password reset email.
 * @param {string} email
 * @returns {Promise<import('axios').AxiosResponse>}
 */
export function requestPasswordReset(email) {
  return apiClient.post('/auth/password-reset/request', { email });
}

/**
 * Confirm a password reset with token and new password.
 * @param {string} token
 * @param {string} newPassword
 * @returns {Promise<import('axios').AxiosResponse>}
 */
export function confirmPasswordReset(token, newPassword) {
  return apiClient.post(`/auth/password-reset/confirm/${token}`, {
    new_password: newPassword,
  });
}
```

- [ ] **Step 2: Create ForgotPassword.vue**

Create `frontend/src/views/ForgotPassword.vue`:

```vue
<template>
  <v-container class="fill-height" fluid>
    <v-row align="center" justify="center">
      <v-col cols="12" sm="8" md="5" lg="4">
        <v-card elevation="4">
          <v-card-title class="text-center pt-6">
            <v-icon size="large" class="mb-2">mdi-lock-reset</v-icon>
            <div>Forgot Password</div>
          </v-card-title>
          <v-card-text>
            <v-alert v-if="submitted" type="info" variant="tonal" class="mb-4">
              If an account exists with that email, a reset link has been sent.
            </v-alert>

            <v-alert
              v-if="isDev && devToken"
              type="warning"
              variant="tonal"
              class="mb-4"
              title="Dev-only: Reset Token"
            >
              <a :href="resetUrl" class="text-break">{{ resetUrl }}</a>
            </v-alert>

            <v-form v-if="!submitted" @submit.prevent="handleSubmit">
              <v-text-field
                v-model="email"
                label="Email address"
                type="email"
                prepend-inner-icon="mdi-email"
                :rules="[rules.required, rules.email]"
                density="compact"
                class="mb-3"
              />
              <v-btn
                type="submit"
                color="primary"
                block
                :loading="loading"
                :disabled="!email"
              >
                Send Reset Link
              </v-btn>
            </v-form>

            <div class="text-center mt-4">
              <router-link to="/login" class="text-decoration-none">
                Back to Login
              </router-link>
            </div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup>
import { ref, computed } from 'vue';
import { requestPasswordReset } from '@/api';

const email = ref('');
const loading = ref(false);
const submitted = ref(false);
const devToken = ref(null);
const isDev = import.meta.env.DEV;

const resetUrl = computed(() =>
  devToken.value ? `${window.location.origin}/reset-password/${devToken.value}` : '',
);

const rules = {
  required: (v) => !!v || 'Required',
  email: (v) => /.+@.+\..+/.test(v) || 'Invalid email',
};

async function handleSubmit() {
  loading.value = true;
  try {
    const response = await requestPasswordReset(email.value);
    submitted.value = true;
    if (response.data.token) {
      devToken.value = response.data.token;
    }
  } catch (err) {
    // Still show "sent" message for anti-enumeration
    submitted.value = true;
    window.logService?.error('Password reset request failed', { error: err.message });
  } finally {
    loading.value = false;
  }
}
</script>
```

- [ ] **Step 3: Create ResetPassword.vue**

Create `frontend/src/views/ResetPassword.vue`:

```vue
<template>
  <v-container class="fill-height" fluid>
    <v-row align="center" justify="center">
      <v-col cols="12" sm="8" md="5" lg="4">
        <v-card elevation="4">
          <v-card-title class="text-center pt-6">
            <v-icon size="large" class="mb-2">mdi-lock-check</v-icon>
            <div>Reset Password</div>
          </v-card-title>
          <v-card-text>
            <v-alert v-if="success" type="success" variant="tonal" class="mb-4">
              Password reset successful. Redirecting to login...
            </v-alert>

            <v-alert v-if="error" type="error" variant="tonal" class="mb-4">
              {{ error }}
            </v-alert>

            <v-form v-if="!success" @submit.prevent="handleSubmit">
              <v-text-field
                v-model="newPassword"
                label="New Password"
                type="password"
                prepend-inner-icon="mdi-lock"
                :rules="[rules.required, rules.minLength]"
                density="compact"
                class="mb-3"
              />
              <v-text-field
                v-model="confirmPassword"
                label="Confirm Password"
                type="password"
                prepend-inner-icon="mdi-lock-check"
                :rules="[rules.required, rules.match]"
                density="compact"
                class="mb-3"
              />
              <v-btn
                type="submit"
                color="primary"
                block
                :loading="loading"
                :disabled="!newPassword || !confirmPassword"
              >
                Reset Password
              </v-btn>
            </v-form>

            <div class="text-center mt-4">
              <router-link to="/forgot-password" class="text-decoration-none">
                Request a new reset link
              </router-link>
            </div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup>
import { ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { confirmPasswordReset } from '@/api';

const route = useRoute();
const router = useRouter();

const newPassword = ref('');
const confirmPassword = ref('');
const loading = ref(false);
const success = ref(false);
const error = ref('');

const rules = {
  required: (v) => !!v || 'Required',
  minLength: (v) => (v && v.length >= 8) || 'Minimum 8 characters',
  match: (v) => v === newPassword.value || 'Passwords do not match',
};

async function handleSubmit() {
  if (newPassword.value !== confirmPassword.value) return;

  loading.value = true;
  error.value = '';
  try {
    await confirmPasswordReset(route.params.token, newPassword.value);
    success.value = true;
    setTimeout(() => router.push('/login'), 2000);
  } catch (err) {
    const detail = err.response?.data?.detail || 'Reset failed. The link may have expired.';
    error.value = detail;
    window.logService?.error('Password reset confirm failed', { error: detail });
  } finally {
    loading.value = false;
  }
}
</script>
```

- [ ] **Step 4: Add routes to router**

In `frontend/src/router/index.js`, add the new routes (anonymous — no `requiresAuth`):

```javascript
{
  path: '/forgot-password',
  name: 'ForgotPassword',
  component: () => import('@/views/ForgotPassword.vue'),
  meta: { title: 'Forgot Password' },
},
{
  path: '/reset-password/:token',
  name: 'ResetPassword',
  component: () => import('@/views/ResetPassword.vue'),
  meta: { title: 'Reset Password' },
},
```

- [ ] **Step 5: Wire Login.vue forgot-password link**

In `frontend/src/views/Login.vue`, replace the `handleForgotPassword` function body:

```javascript
const handleForgotPassword = () => {
  router.push('/forgot-password');
};
```

Add `router` import if not present:

```javascript
import { useRouter } from 'vue-router';
const router = useRouter();
```

- [ ] **Step 6: Write ForgotPassword tests**

Create `frontend/tests/unit/views/ForgotPassword.spec.js`:

```javascript
import { describe, it, expect, vi } from 'vitest';
import { mount } from '@vue/test-utils';
import { createVuetify } from 'vuetify';
import ForgotPassword from '@/views/ForgotPassword.vue';

vi.mock('@/api', () => ({
  requestPasswordReset: vi.fn().mockResolvedValue({ data: { message: 'sent' } }),
}));

const vuetify = createVuetify();

function mountComponent() {
  return mount(ForgotPassword, {
    global: {
      plugins: [vuetify],
      stubs: { RouterLink: true },
    },
  });
}

describe('ForgotPassword', () => {
  it('renders email input', () => {
    const wrapper = mountComponent();
    expect(wrapper.find('input[type="email"]').exists()).toBe(true);
  });

  it('shows confirmation after submit', async () => {
    const wrapper = mountComponent();
    const input = wrapper.find('input[type="email"]');
    await input.setValue('test@example.com');
    await wrapper.find('form').trigger('submit.prevent');
    // Wait for async
    await wrapper.vm.$nextTick();
    await new Promise((r) => setTimeout(r, 50));
    expect(wrapper.text()).toContain('If an account exists');
  });

  it('shows back to login link', () => {
    const wrapper = mountComponent();
    expect(wrapper.text()).toContain('Back to Login');
  });
});
```

- [ ] **Step 7: Write ResetPassword tests**

Create `frontend/tests/unit/views/ResetPassword.spec.js`:

```javascript
import { describe, it, expect, vi } from 'vitest';
import { mount } from '@vue/test-utils';
import { createVuetify } from 'vuetify';
import ResetPassword from '@/views/ResetPassword.vue';

vi.mock('@/api', () => ({
  confirmPasswordReset: vi.fn().mockResolvedValue({ data: { message: 'ok' } }),
}));

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { token: 'test-token-123' } }),
  useRouter: () => ({ push: vi.fn() }),
}));

const vuetify = createVuetify();

function mountComponent() {
  return mount(ResetPassword, {
    global: {
      plugins: [vuetify],
      stubs: { RouterLink: true },
    },
  });
}

describe('ResetPassword', () => {
  it('renders password inputs', () => {
    const wrapper = mountComponent();
    const inputs = wrapper.findAll('input[type="password"]');
    expect(inputs.length).toBe(2);
  });

  it('shows request new link', () => {
    const wrapper = mountComponent();
    expect(wrapper.text()).toContain('Request a new reset link');
  });
});
```

- [ ] **Step 8: Run frontend tests**

```bash
cd frontend
npm test
```

Expected: All tests pass including the new ones.

- [ ] **Step 9: Run frontend lint + format**

```bash
cd frontend
make check
```

- [ ] **Step 10: Commit**

```bash
git add frontend/src/views/ForgotPassword.vue frontend/src/views/ResetPassword.vue frontend/src/api/domain/auth.js frontend/src/router/index.js frontend/src/views/Login.vue frontend/tests/unit/views/ForgotPassword.spec.js frontend/tests/unit/views/ResetPassword.spec.js
git commit -m "feat(frontend): add ForgotPassword and ResetPassword views"
```

---

## Task 11: Frontend — AcceptInvite + VerifyEmail views

**Commit message:** `feat(frontend): add AcceptInvite and VerifyEmail views`

**Files:**
- Create: `frontend/src/views/AcceptInvite.vue`
- Create: `frontend/src/views/VerifyEmail.vue`
- Modify: `frontend/src/api/domain/auth.js`
- Modify: `frontend/src/router/index.js`
- Create: `frontend/tests/unit/views/AcceptInvite.spec.js`
- Create: `frontend/tests/unit/views/VerifyEmail.spec.js`

- [ ] **Step 1: Add API functions**

Add to `frontend/src/api/domain/auth.js`:

```javascript
/**
 * Accept an invite and create user account.
 * @param {string} token
 * @param {string} username
 * @param {string} password
 * @param {string} fullName
 * @returns {Promise<import('axios').AxiosResponse>}
 */
export function acceptInvite(token, username, password, fullName) {
  return apiClient.post(`/auth/invite/accept/${token}`, {
    username,
    password,
    full_name: fullName,
  });
}

/**
 * Verify email with token.
 * @param {string} token
 * @returns {Promise<import('axios').AxiosResponse>}
 */
export function verifyEmail(token) {
  return apiClient.post(`/auth/verify-email/${token}`);
}

/**
 * Resend email verification (authenticated).
 * @returns {Promise<import('axios').AxiosResponse>}
 */
export function resendVerification() {
  return apiClient.post('/auth/verify-email/resend');
}

/**
 * Send an invite to a new user (admin only).
 * @param {string} email
 * @param {string} role
 * @returns {Promise<import('axios').AxiosResponse>}
 */
export function sendInvite(email, role) {
  return apiClient.post('/auth/users/invite', { email, role });
}
```

- [ ] **Step 2: Create AcceptInvite.vue**

Create `frontend/src/views/AcceptInvite.vue`:

```vue
<template>
  <v-container class="fill-height" fluid>
    <v-row align="center" justify="center">
      <v-col cols="12" sm="8" md="5" lg="4">
        <v-card elevation="4">
          <v-card-title class="text-center pt-6">
            <v-icon size="large" class="mb-2">mdi-account-plus</v-icon>
            <div>Accept Invite</div>
          </v-card-title>
          <v-card-text>
            <v-alert v-if="success" type="success" variant="tonal" class="mb-4">
              Account created! Redirecting to login...
            </v-alert>

            <v-alert v-if="error" type="error" variant="tonal" class="mb-4">
              {{ error }}
            </v-alert>

            <div v-if="inviteEmail" class="text-caption text-grey mb-3">
              Invite for: <strong>{{ inviteEmail }}</strong>
            </div>

            <v-form v-if="!success" @submit.prevent="handleSubmit">
              <v-text-field
                v-model="username"
                label="Username"
                prepend-inner-icon="mdi-account"
                :rules="[rules.required, rules.minLength3]"
                density="compact"
                class="mb-3"
              />
              <v-text-field
                v-model="fullName"
                label="Full Name"
                prepend-inner-icon="mdi-badge-account"
                density="compact"
                class="mb-3"
              />
              <v-text-field
                v-model="password"
                label="Password"
                type="password"
                prepend-inner-icon="mdi-lock"
                :rules="[rules.required, rules.minLength8]"
                density="compact"
                class="mb-3"
              />
              <v-text-field
                v-model="confirmPassword"
                label="Confirm Password"
                type="password"
                prepend-inner-icon="mdi-lock-check"
                :rules="[rules.required, rules.match]"
                density="compact"
                class="mb-3"
              />
              <v-btn
                type="submit"
                color="primary"
                block
                :loading="loading"
                :disabled="!username || !password || !confirmPassword"
              >
                Create Account
              </v-btn>
            </v-form>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup>
import { ref, computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { acceptInvite } from '@/api';

const route = useRoute();
const router = useRouter();

const username = ref('');
const fullName = ref('');
const password = ref('');
const confirmPassword = ref('');
const loading = ref(false);
const success = ref(false);
const error = ref('');

const inviteEmail = computed(() => route.query.email || '');

const rules = {
  required: (v) => !!v || 'Required',
  minLength3: (v) => (v && v.length >= 3) || 'Minimum 3 characters',
  minLength8: (v) => (v && v.length >= 8) || 'Minimum 8 characters',
  match: (v) => v === password.value || 'Passwords do not match',
};

async function handleSubmit() {
  if (password.value !== confirmPassword.value) return;

  loading.value = true;
  error.value = '';
  try {
    await acceptInvite(route.params.token, username.value, password.value, fullName.value);
    success.value = true;
    setTimeout(() => router.push('/login'), 2000);
  } catch (err) {
    const detail = err.response?.data?.detail || 'Failed to accept invite.';
    error.value = detail;
    window.logService?.error('Invite accept failed', { error: detail });
  } finally {
    loading.value = false;
  }
}
</script>
```

- [ ] **Step 3: Create VerifyEmail.vue**

Create `frontend/src/views/VerifyEmail.vue`:

```vue
<template>
  <v-container class="fill-height" fluid>
    <v-row align="center" justify="center">
      <v-col cols="12" sm="8" md="5" lg="4">
        <v-card elevation="4">
          <v-card-title class="text-center pt-6">
            <v-icon size="large" class="mb-2">mdi-email-check</v-icon>
            <div>Email Verification</div>
          </v-card-title>
          <v-card-text class="text-center">
            <v-progress-circular v-if="loading" indeterminate color="primary" class="mb-4" />

            <v-alert v-if="success" type="success" variant="tonal" class="mb-4">
              Email verified successfully!
            </v-alert>

            <v-alert v-if="error" type="error" variant="tonal" class="mb-4">
              {{ error }}
            </v-alert>

            <div class="mt-4">
              <router-link to="/login" class="text-decoration-none">
                Go to Login
              </router-link>
            </div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { useRoute } from 'vue-router';
import { verifyEmail } from '@/api';

const route = useRoute();

const loading = ref(true);
const success = ref(false);
const error = ref('');

onMounted(async () => {
  try {
    await verifyEmail(route.params.token);
    success.value = true;
  } catch (err) {
    const detail = err.response?.data?.detail || 'Verification failed. The link may have expired.';
    error.value = detail;
    window.logService?.error('Email verification failed', { error: detail });
  } finally {
    loading.value = false;
  }
});
</script>
```

- [ ] **Step 4: Add routes**

In `frontend/src/router/index.js`:

```javascript
{
  path: '/accept-invite/:token',
  name: 'AcceptInvite',
  component: () => import('@/views/AcceptInvite.vue'),
  meta: { title: 'Accept Invite' },
},
{
  path: '/verify-email/:token',
  name: 'VerifyEmail',
  component: () => import('@/views/VerifyEmail.vue'),
  meta: { title: 'Verify Email' },
},
```

- [ ] **Step 5: Write AcceptInvite tests**

Create `frontend/tests/unit/views/AcceptInvite.spec.js`:

```javascript
import { describe, it, expect, vi } from 'vitest';
import { mount } from '@vue/test-utils';
import { createVuetify } from 'vuetify';
import AcceptInvite from '@/views/AcceptInvite.vue';

vi.mock('@/api', () => ({
  acceptInvite: vi.fn().mockResolvedValue({ data: { username: 'newuser' } }),
}));

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { token: 'invite-token' }, query: { email: 'test@example.com' } }),
  useRouter: () => ({ push: vi.fn() }),
}));

const vuetify = createVuetify();

function mountComponent() {
  return mount(AcceptInvite, {
    global: {
      plugins: [vuetify],
      stubs: { RouterLink: true },
    },
  });
}

describe('AcceptInvite', () => {
  it('renders username and password inputs', () => {
    const wrapper = mountComponent();
    const inputs = wrapper.findAll('input');
    expect(inputs.length).toBeGreaterThanOrEqual(3); // username, fullName, password, confirm
  });

  it('shows invite email from query param', () => {
    const wrapper = mountComponent();
    expect(wrapper.text()).toContain('test@example.com');
  });

  it('renders create account button', () => {
    const wrapper = mountComponent();
    expect(wrapper.text()).toContain('Create Account');
  });
});
```

- [ ] **Step 6: Write VerifyEmail tests**

Create `frontend/tests/unit/views/VerifyEmail.spec.js`:

```javascript
import { describe, it, expect, vi } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import { createVuetify } from 'vuetify';
import VerifyEmail from '@/views/VerifyEmail.vue';

const mockVerifyEmail = vi.fn();

vi.mock('@/api', () => ({
  verifyEmail: (...args) => mockVerifyEmail(...args),
}));

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { token: 'verify-token-123' } }),
}));

const vuetify = createVuetify();

function mountComponent() {
  return mount(VerifyEmail, {
    global: {
      plugins: [vuetify],
      stubs: { RouterLink: true },
    },
  });
}

describe('VerifyEmail', () => {
  it('auto-consumes token on mount and shows success', async () => {
    mockVerifyEmail.mockResolvedValueOnce({ data: { message: 'ok' } });
    const wrapper = mountComponent();
    await flushPromises();
    expect(mockVerifyEmail).toHaveBeenCalledWith('verify-token-123');
    expect(wrapper.text()).toContain('verified successfully');
  });

  it('shows error for invalid token', async () => {
    mockVerifyEmail.mockRejectedValueOnce({
      response: { data: { detail: 'Token expired' } },
    });
    const wrapper = mountComponent();
    await flushPromises();
    expect(wrapper.text()).toContain('Token expired');
  });
});
```

- [ ] **Step 7: Run frontend tests + lint**

```bash
cd frontend
make check
```

Expected: All tests pass.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/views/AcceptInvite.vue frontend/src/views/VerifyEmail.vue frontend/src/api/domain/auth.js frontend/src/router/index.js frontend/tests/unit/views/AcceptInvite.spec.js frontend/tests/unit/views/VerifyEmail.spec.js
git commit -m "feat(frontend): add AcceptInvite and VerifyEmail views"
```

---

## Task 12: Frontend — Invite User dialog on AdminUsers

**Commit message:** `feat(frontend): add Invite User dialog to AdminUsers`

**Files:**
- Create: `frontend/src/components/admin/UserInviteDialog.vue`
- Modify: `frontend/src/views/AdminUsers.vue`

- [ ] **Step 1: Create UserInviteDialog.vue**

Create `frontend/src/components/admin/UserInviteDialog.vue`:

```vue
<template>
  <v-dialog :model-value="modelValue" max-width="500" @update:model-value="$emit('update:modelValue', $event)">
    <v-card>
      <v-card-title>
        <v-icon class="mr-2">mdi-email-fast</v-icon>
        Invite User
      </v-card-title>
      <v-card-text>
        <v-alert v-if="success" type="success" variant="tonal" class="mb-4">
          Invite sent to {{ email }}
        </v-alert>
        <v-alert v-if="error" type="error" variant="tonal" class="mb-4">
          {{ error }}
        </v-alert>
        <v-form v-if="!success" ref="formRef" @submit.prevent="handleSubmit">
          <v-text-field
            v-model="email"
            label="Email address"
            type="email"
            :rules="[rules.required, rules.email]"
            density="compact"
            class="mb-3"
          />
          <v-select
            v-model="role"
            :items="['viewer', 'curator', 'admin']"
            label="Role"
            density="compact"
          />
        </v-form>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="handleClose">
          {{ success ? 'Close' : 'Cancel' }}
        </v-btn>
        <v-btn v-if="!success" color="primary" variant="tonal" :loading="loading" @click="handleSubmit">
          Send Invite
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref } from 'vue';
import { sendInvite } from '@/api';

defineProps({
  modelValue: { type: Boolean, default: false },
});

const emit = defineEmits(['update:modelValue', 'invited']);

const email = ref('');
const role = ref('viewer');
const loading = ref(false);
const success = ref(false);
const error = ref('');

const rules = {
  required: (v) => !!v || 'Required',
  email: (v) => /.+@.+\..+/.test(v) || 'Invalid email',
};

async function handleSubmit() {
  loading.value = true;
  error.value = '';
  try {
    await sendInvite(email.value, role.value);
    success.value = true;
    emit('invited');
  } catch (err) {
    error.value = err.response?.data?.detail || 'Failed to send invite';
    window.logService?.error('Invite failed', { error: error.value });
  } finally {
    loading.value = false;
  }
}

function handleClose() {
  emit('update:modelValue', false);
  // Reset form after dialog closes
  setTimeout(() => {
    email.value = '';
    role.value = 'viewer';
    success.value = false;
    error.value = '';
  }, 300);
}
</script>
```

- [ ] **Step 2: Add invite button and dialog to AdminUsers.vue**

In `frontend/src/views/AdminUsers.vue`:

Import the dialog:
```javascript
import UserInviteDialog from '@/components/admin/UserInviteDialog.vue';
```

Add state:
```javascript
const showInviteDialog = ref(false);
```

Add the button in the template (alongside existing create button):
```vue
<v-btn size="small" color="secondary" variant="tonal" class="mr-2" @click="showInviteDialog = true">
  <v-icon start size="small">mdi-email-fast</v-icon>
  Invite User
</v-btn>
```

Add the dialog in the template:
```vue
<UserInviteDialog v-model="showInviteDialog" @invited="fetchUsers" />
```

- [ ] **Step 3: Run frontend tests + lint**

```bash
cd frontend
make check
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/admin/UserInviteDialog.vue frontend/src/views/AdminUsers.vue
git commit -m "feat(frontend): add Invite User dialog to AdminUsers"
```

---

## Task 13: Exit documentation + Wave 6 plan update

**Commit message:** `docs: add Wave 5c exit note and update Wave 6 plan with SMTP findings`

**Files:**
- Create: `docs/refactor/wave-5c-exit.md`
- Create: `docs/refactor/wave-5-exit.md`
- Modify: `docs/superpowers/plans/2026-04-10-wave-6-tooling-evolution.md`

- [ ] **Step 1: Capture final test counts**

```bash
cd backend && uv run pytest --co -q 2>/dev/null | tail -3
cd ../frontend && npx vitest --run 2>&1 | tail -5
cd ../backend && uv run pytest -k verify tests/test_http_surface_baseline.py -v 2>&1 | tail -5
```

Record the numbers for the exit note.

- [ ] **Step 2: Write wave-5c-exit.md**

Create `docs/refactor/wave-5c-exit.md` following the pattern of `wave-5b-exit.md`. Include:
- Test count entry vs exit
- HTTP baseline count
- What landed (13 commits listed)
- Exit criteria checklist (all green)
- Wave 5a/5b invariants preserved
- What was deferred (SMTPEmailSender, Mailpit, password strength meter)
- Entry conditions for Wave 6

- [ ] **Step 3: Write wave-5-exit.md consolidated summary**

Create `docs/refactor/wave-5-exit.md` summarizing all three PRs:
- Wave 5a (PR #232): Foundations
- Wave 5b (PR #234): User Management
- Wave 5c (PR #TBD): Identity Lifecycle
- Combined test delta
- Combined HTTP baseline delta
- Wave 5 success definition checklist (from scope doc §8)

- [ ] **Step 4: Update Wave 6 plan with SMTP findings**

In `docs/superpowers/plans/2026-04-10-wave-6-tooling-evolution.md`, add a section documenting:
- Mailpit setup for `docker-compose.dev.yml` (image `axllent/mailpit:v1.29.6`, ports 1025/8025, env `MP_SMTP_AUTH_ACCEPT_ANY=1`)
- `SMTPEmailSender` implementation using `aiosmtplib`
- Provider quick-reference table (SendGrid, Mailgun, AWS SES, Gmail, local relay)
- Outbound mail rate limiting config (`email.rate_limit.max_per_minute`, `max_per_hour`)
- Email HTML templates (Jinja2 or string-based)
- The `email.backend: "smtp"` + SMTP env vars are already plumbed from Wave 5c

- [ ] **Step 5: Commit**

```bash
git add docs/refactor/wave-5c-exit.md docs/refactor/wave-5-exit.md docs/superpowers/plans/2026-04-10-wave-6-tooling-evolution.md
git commit -m "docs: add Wave 5c exit note and update Wave 6 plan with SMTP findings"
```

---

## HTTP Baselines

HTTP baselines should be captured after Tasks 6, 7, and 8 are implemented. The baseline capture/verify pattern follows the existing `test_http_surface_baseline.py` framework. Add 5 new capture/verify pairs for:

1. `auth_invite` — `POST /api/v2/auth/users/invite`
2. `auth_invite_accept` — `POST /api/v2/auth/invite/accept/{token}`
3. `auth_password_reset_request` — `POST /api/v2/auth/password-reset/request`
4. `auth_password_reset_confirm` — `POST /api/v2/auth/password-reset/confirm/{token}`
5. `auth_verify_email` — `POST /api/v2/auth/verify-email/{token}`

Add the capture/verify test pairs to `backend/tests/test_http_surface_baseline.py` following the existing `AFFECTED_ENDPOINTS` pattern. Capture baselines with `pytest -k capture`, verify with `pytest -k verify`.

The token-based endpoints require setting up tokens before capture. Use the `CredentialTokenService` to create tokens in the test setup, similar to how `admin_headers` is used for authenticated baselines.

---

## Pre-commit checklist (run before final PR)

```bash
# Backend
cd backend
make check         # ruff lint + mypy + pytest

# Frontend
cd frontend
make check         # vitest + eslint + prettier

# HTTP baselines
cd backend
uv run pytest -k verify tests/test_http_surface_baseline.py -v
```

All must pass before PR creation.
