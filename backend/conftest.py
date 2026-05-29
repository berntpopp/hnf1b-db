"""Root-level pytest configuration.

This conftest runs BEFORE ``tests/conftest.py`` and BEFORE any ``app.*``
modules are imported. Its sole responsibility is to redirect the test suite
at a dedicated test database so that tests never pollute the development
database.

Resolution order for the test database URL:

1. ``TEST_DATABASE_URL`` env var (if set) — used verbatim.
2. ``DATABASE_URL`` env var — used verbatim **only** if the database name
   already contains ``test`` (CI case).
3. ``DATABASE_URL`` with the database name suffixed by ``_test`` — local dev
   fallback (e.g. ``hnf1b_phenopackets`` -> ``hnf1b_phenopackets_test``).
4. A sensible localhost default matching ``docker/docker-compose.dev.yml``.

When running under ``pytest-xdist`` (``PYTEST_XDIST_WORKER`` set, e.g. ``gw0``),
the resolved database name is further suffixed with the worker id so each
worker owns an isolated database (``hnf1b_test`` -> ``hnf1b_test_gw0``). Each
worker database is created and **migrated with Alembic** before any ``app.*``
import builds the engine — never ``metadata.create_all()`` — so the suite's
reliance on migration-seeded reference data and migration behaviour is
preserved. Serial runs (no ``PYTEST_XDIST_WORKER``) are untouched and rely on
the externally-migrated base database, exactly as before.

Once resolved, ``DATABASE_URL`` is overwritten in ``os.environ`` so that any
subsequent import of ``app.core.config.settings`` picks up the test DB. A
runtime assertion then refuses to proceed if the resolved URL does not look
like a dedicated test database.

To bootstrap the local test database, run::

    make db-test-init
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse, urlunparse

_DEFAULT_TEST_URL = (
    "postgresql+asyncpg://hnf1b_user:hnf1b_pass@localhost:5433/hnf1b_phenopackets_test"
)

_BACKEND_DIR = Path(__file__).resolve().parent


def _xdist_worker_id() -> str | None:
    """Return the xdist worker id (e.g. ``gw0``) or ``None`` when serial."""
    return os.environ.get("PYTEST_XDIST_WORKER")


def _derive_test_database_url() -> str:
    """Compute the database URL to use for the test suite.

    Never returns the dev database URL — if the resolved URL does not look
    like a test database, we either rewrite it or replace it outright. When
    running under pytest-xdist, the database name is suffixed with the worker
    id so each worker owns an isolated, separately-migrated database.
    """
    explicit = os.environ.get("TEST_DATABASE_URL")
    if explicit:
        base = explicit
    else:
        base = os.environ.get("DATABASE_URL")
        if not base:
            base = _DEFAULT_TEST_URL
        else:
            parsed = urlparse(base)
            db_path = parsed.path.lstrip("/")
            # CI already passes a test DB via DATABASE_URL — honour it unchanged.
            # Local dev fallback: rewrite to a sibling ``_test`` database.
            if "test" not in db_path.lower():
                new_path = f"/{db_path}_test" if db_path else "/hnf1b_phenopackets_test"
                base = urlunparse(parsed._replace(path=new_path))

    worker = _xdist_worker_id()
    if worker:
        parsed = urlparse(base)
        db_path = parsed.path.lstrip("/")
        base = urlunparse(parsed._replace(path=f"/{db_path}_{worker}"))
    return base


def _sync_dsn_for_admin(async_url: str, database: str) -> str:
    """Build a synchronous psycopg2 DSN pointing at ``database``.

    Used to issue ``CREATE DATABASE`` against the ``postgres`` maintenance DB.
    Strips the ``+asyncpg`` driver suffix so psycopg2 accepts the DSN.
    """
    parsed = urlparse(async_url)
    scheme = parsed.scheme.split("+", 1)[0]
    return urlunparse(parsed._replace(scheme=scheme, path=f"/{database}"))


def _create_worker_database_if_missing(worker_url: str) -> None:
    """Create the per-worker database if it does not already exist.

    Connects to the ``postgres`` maintenance database with psycopg2 in
    autocommit mode (``CREATE DATABASE`` cannot run inside a transaction).
    """
    import psycopg2  # psycopg2-binary is a project dependency.

    target_db = urlparse(worker_url).path.lstrip("/")
    admin_dsn = _sync_dsn_for_admin(worker_url, "postgres")

    conn = psycopg2.connect(admin_dsn)
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (target_db,))
            if cur.fetchone() is None:
                # Identifier is derived from our own worker id + the
                # CI-provided base name, not user input; quote defensively.
                cur.execute(f'CREATE DATABASE "{target_db}"')
    finally:
        conn.close()


def _alembic_upgrade(worker_url: str) -> None:
    """Run ``alembic upgrade head`` against ``worker_url`` in a subprocess.

    A subprocess gets a fresh interpreter that reads ``DATABASE_URL`` from the
    environment (see ``alembic/env.py``), so it is unaffected by any
    already-imported, cached ``app.core.config.settings`` in the worker
    process. Mirrors the ``backend/Makefile`` ``db-test-init`` target.
    """
    env = dict(os.environ)
    env["DATABASE_URL"] = worker_url
    env["TEST_DATABASE_URL"] = worker_url
    env.setdefault("JWT_SECRET", "test-secret-key-for-local-pytest")
    env.setdefault("ADMIN_PASSWORD", "TestAdminPass!2026")
    env.setdefault("ENVIRONMENT", "development")
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=_BACKEND_DIR,
        env=env,
        check=True,
    )


def _maybe_set_worker_redis_url() -> None:
    """Give each xdist worker its own Redis logical DB to avoid cross-talk.

    Derives an index from the numeric part of the worker id and keeps it
    within Redis's default 16 logical databases.
    """
    worker = _xdist_worker_id()
    if not worker:
        return
    digits = "".join(ch for ch in worker if ch.isdigit())
    index = (int(digits) if digits else 0) % 16
    base = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    parsed = urlparse(base)
    os.environ["REDIS_URL"] = urlunparse(parsed._replace(path=f"/{index}"))


def _ensure_test_database_url() -> None:
    """Install the resolved test DB URL and verify it is safe.

    Called at module import time so that every subsequent ``from app.*``
    import — including the one in ``tests/conftest.py`` — sees the test
    database URL rather than the developer's working database. Under xdist,
    each worker creates and Alembic-migrates its own database first.
    """
    resolved = _derive_test_database_url()

    parsed = urlparse(resolved)
    db_name = parsed.path.lstrip("/").lower()

    # Hard safety rail: the word "test" must appear in the database name.
    # This refuses to run tests against databases like ``hnf1b_phenopackets``
    # which developers may have populated with real data.
    if "test" not in db_name:
        raise RuntimeError(
            "Refusing to run backend tests: resolved DATABASE_URL "
            f"database name {db_name!r} does not contain 'test'. "
            "Set TEST_DATABASE_URL to a dedicated test database "
            "(e.g. hnf1b_phenopackets_test) or run `make db-test-init`."
        )

    # Under xdist, each worker creates + Alembic-migrates its own database
    # BEFORE app.database builds the engine in tests/conftest.py. Without this,
    # the worker DB would not exist (only the base DB is migrated by CI).
    if _xdist_worker_id():
        _create_worker_database_if_missing(resolved)
        _alembic_upgrade(resolved)
        _maybe_set_worker_redis_url()

    os.environ["DATABASE_URL"] = resolved
    # Keep TEST_DATABASE_URL aligned so downstream tooling sees the same value.
    os.environ.setdefault("TEST_DATABASE_URL", resolved)

    # JWT_SECRET is required by app.core.config validation. Provide a
    # deterministic fallback for local test runs that do not copy .env in.
    os.environ.setdefault("JWT_SECRET", "test-secret-key-for-local-pytest")
    # Avoid the production admin-password validator tripping during tests.
    os.environ.setdefault("ADMIN_PASSWORD", "TestAdminPass!2026")
    # Set environment to "development" so dev-only features (e.g. raw invite
    # tokens in responses) are available during tests.
    os.environ.setdefault("ENVIRONMENT", "development")


_ensure_test_database_url()
